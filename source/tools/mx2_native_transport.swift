import Foundation
import CoreMIDI
import IOKit.hid
import Darwin

private let virtualName = "MX2 for djay"
private let lock = NSLock()
private func emit(_ event: String, _ values: [String: Any] = [:]) {
    var record = values
    record["event"] = event
    record["monotonic_ns"] = DispatchTime.now().uptimeNanoseconds
    lock.lock()
    defer { lock.unlock() }
    if let data = try? JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]) {
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([10]))
    }
}
private func packetCopies(_ list: UnsafePointer<MIDIPacketList>) -> [(UInt64, [UInt8])] {
    let offset = MemoryLayout<MIDIPacketList>.offset(of: \MIDIPacketList.packet)!
    var packet = UnsafeRawPointer(list).advanced(by: offset).assumingMemoryBound(to: MIDIPacket.self)
    var result: [(UInt64, [UInt8])] = []
    for _ in 0..<list.pointee.numPackets {
        let dataOffset = MemoryLayout<MIDIPacket>.offset(of: \MIDIPacket.data)!
        let data = UnsafeRawPointer(packet).advanced(by: dataOffset).assumingMemoryBound(to: UInt8.self)
        result.append((packet.pointee.timeStamp, Array(UnsafeBufferPointer(start: data, count: Int(packet.pointee.length)))))
        packet = UnsafePointer(MIDIPacketNext(packet))
    }
    return result
}
private enum Command {
    case virtual([UInt8])
    case leds([UInt8])
}
private func parse(_ line: String) -> Command? {
    guard let data = line.data(using: .utf8),
          let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
          let target = object["to"] as? String,
          let values = object["bytes"] as? [NSNumber], !values.isEmpty, values.count <= 255 else { return nil }
    var bytes: [UInt8] = []
    for value in values {
        guard CFGetTypeID(value) != CFBooleanGetTypeID(), value.doubleValue.isFinite,
              value.doubleValue == Double(value.intValue), (0...255).contains(value.intValue) else { return nil }
        bytes.append(UInt8(value.intValue))
    }
    if target == "hid-leds" {
        guard bytes.count == 105, bytes.allSatisfy({ $0 <= 127 }) else { return nil }
        return .leds(bytes)
    }
    guard target == "virtual", bytes.count % 3 == 0 else { return nil }
    for i in stride(from: 0, to: bytes.count, by: 3) {
        guard [UInt8(0x80), 0x90, 0xb0].contains(bytes[i] & 0xf0), bytes[i + 1] < 128, bytes[i + 2] < 128 else { return nil }
    }
    return .virtual(bytes)
}
private func numericProperty(_ device: IOHIDDevice, _ key: String) -> Int? {
    (IOHIDDeviceGetProperty(device, key as CFString) as? NSNumber)?.intValue
}
private func isMX2(_ device: IOHIDDevice) -> Bool {
    numericProperty(device, kIOHIDVendorIDKey) == 0x17cc &&
    numericProperty(device, kIOHIDProductIDKey) == 0x2420 &&
    numericProperty(device, kIOHIDPrimaryUsagePageKey) == 0xff01 &&
    numericProperty(device, kIOHIDPrimaryUsageKey) == 0
}
private final class NativeTransport {
    private let observer: Bool
    init(observer: Bool = false) { self.observer = observer }
    private var physicalPort: MIDIPortRef = 0
    private var physicalSources: Set<MIDIEndpointRef> = []
    private var scanTimer: DispatchSourceTimer?
    private var client: MIDIClientRef = 0
    private var source: MIDIEndpointRef = 0
    private var destination: MIDIEndpointRef = 0
    private let manager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
    private var managerOpened = false
    private var candidates: [UInt32: IOHIDDevice] = [:]
    private var device: IOHIDDevice?
    private var buffer: UnsafeMutablePointer<UInt8>?
    private var bufferSize = 0
    private var stopped = false
    private var signals: [DispatchSourceSignal] = []
    private let runLoop = CFRunLoopGetCurrent()!

    private func check(_ status: OSStatus, _ operation: String) -> Bool {
        if status != 0 { emit("error", ["operation": operation, "status": status]) }
        return status == 0
    }
    private func identifier(_ device: IOHIDDevice) -> String { "hid-service-\(IOHIDDeviceGetService(device))" }

    func start() -> Bool {
        if !observer { for i in 0..<MIDIGetNumberOfSources() {
            let endpoint = MIDIGetSource(i)
            var value: Unmanaged<CFString>?
            if MIDIObjectGetStringProperty(endpoint, kMIDIPropertyName, &value) == noErr,
               let name = value?.takeRetainedValue(), name as String == virtualName {
                emit("error", ["operation": "existing_bridge", "message": "MX2 for djay already exists. Stop the other MX2 bridge before starting this app."])
                return false
            }
        } }
        let context = Unmanaged.passUnretained(self).toOpaque()
        IOHIDManagerSetDeviceMatching(manager, [kIOHIDVendorIDKey: 0x17cc, kIOHIDProductIDKey: 0x2420,
                                               kIOHIDPrimaryUsagePageKey: 0xff01, kIOHIDPrimaryUsageKey: 0] as CFDictionary)
        IOHIDManagerRegisterDeviceMatchingCallback(manager, { context, _, _, device in
            guard let context = context else { return }
            let owner = Unmanaged<NativeTransport>.fromOpaque(context).takeUnretainedValue()
            owner.add(device)
        }, context)
        IOHIDManagerRegisterDeviceRemovalCallback(manager, { context, _, _, device in
            guard let context = context else { return }
            let owner = Unmanaged<NativeTransport>.fromOpaque(context).takeUnretainedValue()
            owner.remove(device)
        }, context)
        IOHIDManagerScheduleWithRunLoop(manager, runLoop, CFRunLoopMode.defaultMode.rawValue)
        guard check(IOHIDManagerOpen(manager, IOOptionBits(kIOHIDOptionsTypeNone)), "open_hid_manager") else { cleanup(); return false }
        managerOpened = true
        let found = (IOHIDManagerCopyDevices(manager) as? Set<IOHIDDevice>) ?? []
        for device in found where isMX2(device) { candidates[IOHIDDeviceGetService(device)] = device }
        if candidates.count > 1 && !observer {
            emit("error", ["operation": "select_hid", "matching_devices": candidates.count,
                           "message": "Expected exactly one VID17cc PID2420 usageff01/0 device"])
            cleanup()
            return false
        }
        if candidates.count == 1 {
            if !connectSelected() && !observer { cleanup(); return false }
        } else {
            emit("hardware_unavailable", ["message": "Connect one MX2. Virtual MIDI endpoints remain available while waiting."])
        }
        if observer { return startObserverMIDI() }
        guard check(MIDIClientCreate("MX2 native bridge" as CFString, nil, nil, &client), "create_midi_client"),
              check(MIDISourceCreate(client, virtualName as CFString, &source), "create_virtual_source"),
              check(MIDIDestinationCreateWithBlock(client, virtualName as CFString, &destination, { [weak self] list, _ in
                  let copied = packetCopies(list)
                  DispatchQueue.main.async { [weak self] in
                      guard let self = self, !self.stopped else { return }
                      for (timestamp, bytes) in copied { emit("feedback", ["bytes": bytes, "midi_timestamp": timestamp]) }
                  }
              }), "create_virtual_destination") else { cleanup(); return false }
        for endpoint in [source, destination] {
            _ = MIDIObjectSetStringProperty(endpoint, kMIDIPropertyManufacturer, "MX2 Bridge" as CFString)
        }
        emit("ready_native", ["virtual_name": virtualName, "vendor_id": 0x17cc, "product_id": 0x2420,
                               "usage_page": 0xff01, "usage": 0, "manual_app_mode_required": true,
                               "automatic_mode_switch": false, "device_id": device.map { identifier($0) } ?? "not-connected"])
        return true
    }

    private func startObserverMIDI() -> Bool {
        guard check(MIDIClientCreate("MX2 passive observer" as CFString, nil, nil, &client), "create_observer_client"),
              check(MIDIInputPortCreateWithBlock(client, "MX2 physical input" as CFString, &physicalPort, { [weak self] list, _ in
                  let copies = packetCopies(list)
                  DispatchQueue.main.async { [weak self] in
                      guard let self = self, !self.stopped else { return }
                      for (timestamp, bytes) in copies {
                          emit("physical_midi_input", ["bytes": bytes, "midi_timestamp": timestamp])
                      }
                  }
              }), "create_observer_input") else { cleanup(); return false }
        scanPhysicalSources()
        let timer = DispatchSource.makeTimerSource(queue: .main)
        timer.schedule(deadline: .now() + 1, repeating: 1)
        timer.setEventHandler { [weak self] in
            guard let self = self, !self.stopped else { return }
            self.scanPhysicalSources()
            if self.device == nil && self.candidates.count == 1 { _ = self.connectSelected() }
        }
        scanTimer = timer
        timer.resume()
        emit("ready_observer", ["passive": true, "creates_virtual_ports": false,
                                "automatic_mode_switch": false, "accepts_output_commands": false])
        return true
    }

    private func scanPhysicalSources() {
        guard !stopped, observer, physicalPort != 0 else { return }
        var found: Set<MIDIEndpointRef> = []
        for index in 0..<MIDIGetNumberOfSources() {
            let endpoint = MIDIGetSource(index)
            var name: Unmanaged<CFString>?
            guard MIDIObjectGetStringProperty(endpoint, kMIDIPropertyName, &name) == noErr,
                  let retainedName = name else { continue }
            if retainedName.takeRetainedValue() as String == "Traktor MX2" { found.insert(endpoint) }
        }
        // Refuse multiple same-name physical devices rather than mixing their modes.
        if found.count != 1 { found.removeAll() }
        for old in physicalSources.subtracting(found) { _ = MIDIPortDisconnectSource(physicalPort, old) }
        var connected = physicalSources.intersection(found)
        for new in found.subtracting(physicalSources) {
            if check(MIDIPortConnectSource(physicalPort, new, nil), "observe_physical_midi") {
                connected.insert(new)
                emit("physical_midi_connected", ["endpoint": new])
            }
        }
        physicalSources = connected
    }
    private func add(_ added: IOHIDDevice) {
        guard !stopped, isMX2(added) else { return }
        let key = IOHIDDeviceGetService(added)
        guard candidates[key] == nil else { return }
        candidates[key] = added
        emit("hid_added", ["id": identifier(added), "matching_devices": candidates.count])
        if candidates.count == 1 { _ = connectSelected() }
        else { closeDevice(); emit("hardware_unavailable", ["message": "Multiple exact MX2 devices; refusing ambiguous routing"]) }
    }
    private func remove(_ removed: IOHIDDevice) {
        guard !stopped else { return }
        let key = IOHIDDeviceGetService(removed)
        candidates.removeValue(forKey: key)
        emit("hid_removed", ["id": identifier(removed), "matching_devices": candidates.count])
        if let current = device, CFEqual(current, removed) { closeDevice() }
        if device == nil, candidates.count == 1 { _ = connectSelected() }
        if device == nil { emit("hardware_unavailable", ["message": "No unique connected MX2; virtual MIDI endpoints remain available"]) }
    }
    private func connectSelected() -> Bool {
        guard candidates.count == 1, let selected = candidates.values.first else { return false }
        if let current = device, CFEqual(current, selected) { return true }
        closeDevice()
        guard check(IOHIDDeviceOpen(selected, IOOptionBits(kIOHIDOptionsTypeNone)), "open_hid_device") else { return false }
        device = selected
        bufferSize = max(64, numericProperty(selected, kIOHIDMaxInputReportSizeKey) ?? 64)
        guard bufferSize <= 65536 else { emit("error", ["message": "Unexpected maximum HID report size"]); closeDevice(); return false }
        buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: bufferSize)
        IOHIDDeviceScheduleWithRunLoop(selected, runLoop, CFRunLoopMode.defaultMode.rawValue)
        IOHIDDeviceRegisterInputReportCallback(selected, buffer!, bufferSize, { context, status, _, _, reportID, bytes, count in
            guard let context = context else { return }
            let owner = Unmanaged<NativeTransport>.fromOpaque(context).takeUnretainedValue()
            guard let device = owner.device, !owner.stopped else { return }
            owner.emitInput(device, status: status, reportID: reportID,
                            bytes: Array(UnsafeBufferPointer(start: bytes, count: max(0, count))), seed: false)
        }, Unmanaged.passUnretained(self).toOpaque())
        emit("hid_connected", ["id": identifier(selected), "exclusive": false])
        for (reportID, size) in [(1, 15), (2, 53)] {
            var bytes = [UInt8](repeating: 0, count: size)
            bytes[0] = UInt8(reportID)
            var count = size
            let status = bytes.withUnsafeMutableBufferPointer { data in
                IOHIDDeviceGetReport(selected, kIOHIDReportTypeInput, CFIndex(reportID), data.baseAddress!, &count)
            }
            emit("seed_status", ["id": identifier(selected), "report_id": reportID, "status": status, "count": count])
            if status == kIOReturnSuccess, count >= 0, count <= size {
                emitInput(selected, status: status, reportID: UInt32(reportID), bytes: Array(bytes.prefix(count)), seed: true)
            }
        }
        return true
    }
    private func emitInput(_ device: IOHIDDevice, status: IOReturn, reportID: UInt32, bytes: [UInt8], seed: Bool) {
        emit("hid_input", ["id": identifier(device), "report_id": reportID,
                           "bytes_hex": bytes.map { String(format: "%02x", $0) }.joined(),
                           "count": bytes.count, "status": status, "seed": seed])
    }

    func accept(_ line: String) {
        guard !stopped else { return }
        guard !observer else {
            emit("error", ["operation": "passive_observer", "message": "Observer accepts no output commands"])
            return
        }
        guard let command = parse(line) else {
            emit("error", ["operation": "validate_command", "message": "Only virtual Note/CC triples or hid-leds exactly105 bytes0..127 are accepted"])
            return
        }
        switch command {
        case .virtual(let bytes):
            var packets = MIDIPacketList()
            let status = withUnsafeMutablePointer(to: &packets) { list -> OSStatus in
                let packet = MIDIPacketListInit(list)
                _ = bytes.withUnsafeBufferPointer { data in
                    MIDIPacketListAdd(list, MemoryLayout<MIDIPacketList>.size, packet, 0, data.count, data.baseAddress!)
                }
                return MIDIReceived(source, list)
            }
            if check(status, "send_virtual") { emit("sent", ["to": "virtual", "bytes": bytes]) }
        case .leds(let payload):
            guard let device = device else { emit("error", ["operation": "send_hid_leds", "message": "No unique connected MX2"]); return }
            let numbered = [UInt8(0x80)] + payload
            let status = numbered.withUnsafeBufferPointer { data in
                IOHIDDeviceSetReport(device, kIOHIDReportTypeOutput, 0x80, data.baseAddress!, data.count)
            }
            emit("hid_led_status", ["id": identifier(device), "status": status, "payload_count": payload.count,
                                     "numbered_count": numbered.count, "report_id": 0x80])
        }
    }
    func installSignals() {
        for number in [SIGINT, SIGTERM] {
            signal(number, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: number, queue: .main)
            source.setEventHandler { [weak self] in self?.stop("signal") }
            signals.append(source)
            source.resume()
        }
        signal(SIGPIPE, SIG_IGN)
    }
    func stop(_ reason: String) {
        guard !stopped else { return }
        stopped = true
        cleanup()
        emit("stopped", ["reason": reason])
        CFRunLoopStop(runLoop)
    }
    private func closeDevice() {
        if let device = device {
            IOHIDDeviceUnscheduleFromRunLoop(device, runLoop, CFRunLoopMode.defaultMode.rawValue)
            _ = IOHIDDeviceClose(device, IOOptionBits(kIOHIDOptionsTypeNone))
        }
        device = nil
        buffer?.deallocate()
        buffer = nil
        bufferSize = 0
    }
    private func cleanup() {
        scanTimer?.cancel(); scanTimer = nil
        if physicalPort != 0 { _ = MIDIPortDispose(physicalPort); physicalPort = 0 }
        physicalSources.removeAll()
        closeDevice()
        IOHIDManagerUnscheduleFromRunLoop(manager, runLoop, CFRunLoopMode.defaultMode.rawValue)
        if managerOpened { _ = IOHIDManagerClose(manager, IOOptionBits(kIOHIDOptionsTypeNone)); managerOpened = false }
        if destination != 0 { _ = MIDIEndpointDispose(destination); destination = 0 }
        if source != 0 { _ = MIDIEndpointDispose(source); source = 0 }
        if client != 0 { _ = MIDIClientDispose(client); client = 0 }
    }
    var isStopped: Bool { stopped }
}

private func selfTest() {
    precondition(parse("{\"to\":\"virtual\",\"bytes\":[144,29,127]}") != nil)
    precondition(parse("{\"to\":\"virtual\",\"bytes\":[240,1,247]}") == nil)
    precondition(parse("{\"to\":\"virtual\",\"bytes\":[144,true,127]}") == nil)
    precondition(parse("{\"to\":\"virtual\",\"bytes\":[144,128,127]}") == nil)
    precondition(parse("{\"to\":\"hardware\",\"bytes\":[144,29,127]}") == nil)
    let valid = try! JSONSerialization.data(withJSONObject: ["to": "hid-leds", "bytes": [Int](repeating: 126, count: 105)])
    precondition(parse(String(data: valid, encoding: .utf8)!) != nil)
    for count in [104, 106] {
        let invalid = try! JSONSerialization.data(withJSONObject: ["to": "hid-leds", "bytes": [Int](repeating: 0, count: count)])
        precondition(parse(String(data: invalid, encoding: .utf8)!) == nil)
    }
    let invalid = try! JSONSerialization.data(withJSONObject: ["to": "hid-leds", "bytes": [Int](repeating: 128, count: 105)])
    precondition(parse(String(data: invalid, encoding: .utf8)!) == nil)
    var list = MIDIPacketList()
    withUnsafeMutablePointer(to: &list) { pointer in
        let packet = MIDIPacketListInit(pointer)
        let bytes: [UInt8] = [144, 29, 127]
        _ = bytes.withUnsafeBufferPointer { data in MIDIPacketListAdd(pointer, MemoryLayout<MIDIPacketList>.size, packet, 77, data.count, data.baseAddress!) }
        let copies = packetCopies(pointer)
        precondition(copies.count == 1 && copies[0].0 == 77 && copies[0].1 == bytes)
    }
    emit("self_test_passed", ["hardware_opened": false, "virtual_ports_created": false])
}
let args = Array(CommandLine.arguments.dropFirst())
if args == ["--self-test"] { selfTest(); exit(0) }
if args == ["--help"] {
    print("Usage: mx2-native-transport [--self-test | --observe]\nManual APP mode required. Creates MX2 for djay virtual source/destination. Emits hid_input and feedback JSONL. Accepts virtual Note/CC or hid-leds105-byte payload only. Never sends mode/feature/firmware commands.")
    exit(0)
}
guard args.isEmpty || args == ["--observe"] else { emit("error", ["message": "Unknown arguments"]); exit(2) }
private let transport = NativeTransport(observer: args == ["--observe"])
guard transport.start() else { exit(1) }
transport.installSignals()
DispatchQueue.global(qos: .userInitiated).async {
    while let line = readLine() { DispatchQueue.main.async { transport.accept(line) } }
    DispatchQueue.main.async { transport.stop("stdin_eof") }
}
while !transport.isStopped { RunLoop.current.run(until: Date(timeIntervalSinceNow: 1)) }
