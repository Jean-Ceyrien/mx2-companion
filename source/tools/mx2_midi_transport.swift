import Foundation
import CoreMIDI
import Darwin

// JSONL transport only. Routing and mode state belong to the Python supervisor.
private let hardwareName = "Traktor MX2"
private let hardwareManufacturer = "Native Instruments"
private let virtualName = "MX2 for djay"
private let outputLock = NSLock()

private func emit(_ event: String, _ values: [String: Any] = [:]) {
    var record = values
    record["event"] = event
    record["monotonic_ns"] = DispatchTime.now().uptimeNanoseconds
    outputLock.lock()
    defer { outputLock.unlock() }
    if let data = try? JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]) {
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([10]))
    }
}

private func property(_ object: MIDIObjectRef, _ key: CFString) -> String {
    var value: Unmanaged<CFString>?
    guard MIDIObjectGetStringProperty(object, key, &value) == noErr else { return "" }
    return value?.takeRetainedValue() as String? ?? ""
}

private func manufacturer(_ endpoint: MIDIEndpointRef) -> String {
    let direct = property(endpoint, kMIDIPropertyManufacturer)
    if !direct.isEmpty { return direct }
    var entity: MIDIEntityRef = 0
    var device: MIDIDeviceRef = 0
    if MIDIEndpointGetEntity(endpoint, &entity) == noErr, entity != 0 {
        let inherited = property(entity, kMIDIPropertyManufacturer)
        if !inherited.isEmpty { return inherited }
        if MIDIEntityGetDevice(entity, &device) == noErr, device != 0 {
            return property(device, kMIDIPropertyManufacturer)
        }
    }
    return ""
}

private func endpoints(_ source: Bool) -> [MIDIEndpointRef] {
    let count = source ? MIDIGetNumberOfSources() : MIDIGetNumberOfDestinations()
    return (0..<count).map { source ? MIDIGetSource($0) : MIDIGetDestination($0) }
}

private func matches(_ endpoint: MIDIEndpointRef) -> Bool {
    property(endpoint, kMIDIPropertyName) == hardwareName && manufacturer(endpoint) == hardwareManufacturer
}

private func inventory() {
    for source in [true, false] {
        for endpoint in endpoints(source) {
            emit("endpoint", ["direction": source ? "source" : "destination",
                              "name": property(endpoint, kMIDIPropertyName),
                              "display_name": property(endpoint, kMIDIPropertyDisplayName),
                              "manufacturer": manufacturer(endpoint), "endpoint_ref": endpoint,
                              "hardware_match": matches(endpoint)])
        }
    }
    emit("inventory_complete", ["matching_sources": endpoints(true).filter(matches).count,
                                "matching_destinations": endpoints(false).filter(matches).count,
                                "virtual_ports_created": false])
}

// Copy packet bytes before leaving CoreMIDI's callback: callback memory is borrowed.
private func copyPackets(_ list: UnsafePointer<MIDIPacketList>) -> [(UInt64, [UInt8])] {
    var result: [(UInt64, [UInt8])] = []
    let packetOffset = MemoryLayout<MIDIPacketList>.offset(of: \MIDIPacketList.packet)!
    var packet = UnsafeRawPointer(list).advanced(by: packetOffset).assumingMemoryBound(to: MIDIPacket.self)
    for _ in 0..<list.pointee.numPackets {
        let dataOffset = MemoryLayout<MIDIPacket>.offset(of: \MIDIPacket.data)!
        let data = UnsafeRawPointer(packet).advanced(by: dataOffset).assumingMemoryBound(to: UInt8.self)
        result.append((packet.pointee.timeStamp,
                       Array(UnsafeBufferPointer(start: data, count: Int(packet.pointee.length)))))
        packet = UnsafePointer(MIDIPacketNext(packet))
    }
    return result
}

private final class Transport {
    private let queue = DispatchQueue(label: "mx2.transport.state")
    private var client: MIDIClientRef = 0
    private var input: MIDIPortRef = 0
    private var output: MIDIPortRef = 0
    private var virtualSource: MIDIEndpointRef = 0
    private var virtualDestination: MIDIEndpointRef = 0
    private var hardwareSource: MIDIEndpointRef = 0
    private var hardwareDestination: MIDIEndpointRef = 0
    private var stopped = false
    private var signalSources: [DispatchSourceSignal] = []

    func start() -> Bool {
        queue.sync {
            var status = MIDIClientCreateWithBlock("MX2 JSONL transport" as CFString, &client) { [weak self] note in
                let id = note.pointee.messageID.rawValue
                self?.queue.async { [weak self] in
                    guard let self = self, !self.stopped else { return }
                    emit("hotplug", ["notification_id": id])
                    self.refreshHardware()
                }
            }
            guard check(status, "create_client") else { dispose(); return false }
            status = MIDIInputPortCreateWithBlock(client, "MX2 hardware input" as CFString, &input) { [weak self] packets, _ in
                self?.receive("input", packets)
            }
            guard check(status, "create_input_port") else { dispose(); return false }
            status = MIDIOutputPortCreate(client, "MX2 hardware output" as CFString, &output)
            guard check(status, "create_output_port") else { dispose(); return false }
            guard refreshHardware() else { dispose(); return false }
            status = MIDISourceCreate(client, virtualName as CFString, &virtualSource)
            guard check(status, "create_virtual_source") else { dispose(); return false }
            status = MIDIDestinationCreateWithBlock(client, virtualName as CFString, &virtualDestination) { [weak self] packets, _ in
                self?.receive("feedback", packets)
            }
            guard check(status, "create_virtual_destination") else { dispose(); return false }
            for endpoint in [virtualSource, virtualDestination] {
                _ = MIDIObjectSetStringProperty(endpoint, kMIDIPropertyManufacturer, "MX2 Bridge" as CFString)
            }
            emit("ready", ["virtual_name": virtualName, "hardware_name": hardwareName,
                           "hardware_manufacturer": hardwareManufacturer,
                           "virtual_source_ref": virtualSource, "virtual_destination_ref": virtualDestination])
            return true
        }
    }

    @discardableResult private func check(_ status: OSStatus, _ operation: String) -> Bool {
        if status != noErr { emit("error", ["operation": operation, "status": status]) }
        return status == noErr
    }

    @discardableResult private func refreshHardware() -> Bool {
        let sources = endpoints(true).filter(matches)
        let destinations = endpoints(false).filter(matches)
        guard sources.count == 1, destinations.count == 1 else {
            if hardwareSource != 0 { _ = MIDIPortDisconnectSource(input, hardwareSource) }
            hardwareSource = 0
            hardwareDestination = 0
            emit("hardware_unavailable", ["matching_sources": sources.count,
                                          "matching_destinations": destinations.count,
                                          "message": "Expected exactly one hardware source and destination with exact name and manufacturer"])
            return false
        }
        let source = sources[0]
        if hardwareSource != source {
            if hardwareSource != 0 { _ = MIDIPortDisconnectSource(input, hardwareSource) }
            hardwareSource = 0
            guard check(MIDIPortConnectSource(input, source, nil), "connect_hardware_source") else {
                hardwareDestination = 0
                return false
            }
            hardwareSource = source
            emit("hardware_connected", ["source_ref": source, "destination_ref": destinations[0]])
        }
        hardwareDestination = destinations[0]
        return true
    }

    private func receive(_ event: String, _ list: UnsafePointer<MIDIPacketList>) {
        let copied = copyPackets(list)
        queue.async { [weak self] in
            guard let self = self, !self.stopped else { return }
            for (timestamp, bytes) in copied {
                emit(event, ["bytes": bytes, "midi_timestamp": timestamp])
            }
        }
    }

    func accept(_ line: String) {
        queue.async { [weak self] in
            guard let self = self, !self.stopped else { return }
            guard let data = line.data(using: .utf8),
                  let record = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                  let destination = record["to"] as? String,
                  destination == "virtual" || destination == "hardware",
                  let numbers = record["bytes"] as? [NSNumber],
                  !numbers.isEmpty, numbers.count <= 255, numbers.count % 3 == 0 else {
                emit("error", ["operation": "validate_command", "message": "Expected to:virtual|hardware and 1..85 complete three-byte Note/CC messages"])
                return
            }
            var bytes: [UInt8] = []
            for number in numbers {
                guard CFGetTypeID(number) != CFBooleanGetTypeID(), number.doubleValue.isFinite,
                      number.doubleValue == Double(number.intValue), (0...255).contains(number.intValue) else {
                    emit("error", ["operation": "validate_command", "message": "bytes must be integer values0..255"])
                    return
                }
                bytes.append(UInt8(number.intValue))
            }
            for index in stride(from: 0, to: bytes.count, by: 3) {
                guard [UInt8(0x80), 0x90, 0xb0].contains(bytes[index] & 0xf0),
                      bytes[index + 1] < 128, bytes[index + 2] < 128 else {
                    emit("error", ["operation": "validate_command", "message": "Only explicit NoteOff, NoteOn and CC messages are allowed; no running status or SysEx"])
                    return
                }
            }
            guard destination != "hardware" || self.hardwareDestination != 0 else {
                emit("error", ["operation": "send_hardware", "message": "Exact matching hardware is unavailable"])
                return
            }
            var packets = MIDIPacketList()
            let status = withUnsafeMutablePointer(to: &packets) { list -> OSStatus in
                let packet = MIDIPacketListInit(list)
                _ = bytes.withUnsafeBufferPointer { buffer in
                    MIDIPacketListAdd(list, MemoryLayout<MIDIPacketList>.size, packet, 0,
                                      buffer.count, buffer.baseAddress!)
                }
                if destination == "virtual" { return MIDIReceived(self.virtualSource, list) }
                return MIDISend(self.output, self.hardwareDestination, list)
            }
            if self.check(status, "send_" + destination) {
                emit("sent", ["to": destination, "bytes": bytes])
            }
        }
    }

    func installSignals() {
        for number in [SIGINT, SIGTERM] {
            signal(number, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: number, queue: queue)
            source.setEventHandler { [weak self] in self?.stop("signal", code: 0) }
            signalSources.append(source)
            source.resume()
        }
        signal(SIGPIPE, SIG_IGN)
    }

    func endOfInput() { queue.async { [weak self] in self?.stop("stdin_eof", code: 0) } }

    private func stop(_ reason: String, code: Int32) {
        guard !stopped else { return }
        stopped = true
        dispose()
        emit("stopped", ["reason": reason])
        exit(code)
    }

    private func dispose() {
        if input != 0, hardwareSource != 0 { _ = MIDIPortDisconnectSource(input, hardwareSource) }
        hardwareSource = 0
        hardwareDestination = 0
        if virtualDestination != 0 { _ = MIDIEndpointDispose(virtualDestination); virtualDestination = 0 }
        if virtualSource != 0 { _ = MIDIEndpointDispose(virtualSource); virtualSource = 0 }
        if input != 0 { _ = MIDIPortDispose(input); input = 0 }
        if output != 0 { _ = MIDIPortDispose(output); output = 0 }
        if client != 0 { _ = MIDIClientDispose(client); client = 0 }
    }
}

let args = Array(CommandLine.arguments.dropFirst())
if args == ["--self-test"] {
    let storage = UnsafeMutableRawPointer.allocate(byteCount: 1024, alignment: MemoryLayout<MIDIPacketList>.alignment)
    defer { storage.deallocate() }
    let list = storage.bindMemory(to: MIDIPacketList.self, capacity: 1)
    var packet = MIDIPacketListInit(list)
    let examples: [[UInt8]] = [[0x90, 29, 127], [0x81, 33, 0, 0xb1, 19, 65]]
    for (index, bytes) in examples.enumerated() {
        packet = bytes.withUnsafeBufferPointer { data in
            MIDIPacketListAdd(list, 1024, packet, MIDITimeStamp(index + 1), data.count, data.baseAddress!)
        }
    }
    let copied = copyPackets(UnsafePointer(list))
    guard copied.count == 2, copied[0].0 == 1, copied[1].0 == 2,
          copied[0].1 == examples[0], copied[1].1 == examples[1] else {
        emit("self_test_failed"); exit(1)
    }
    emit("self_test_passed", ["packets": 2, "bytes": 9, "virtual_ports_created": false])
    exit(0)
}
if args == ["--inventory-only"] { inventory(); exit(0) }
if args == ["--help"] {
    print("Usage: mx2-midi-transport [--inventory-only]\nDefault creates bidirectional virtual endpoints named MX2 for djay; routes only explicit stdin commands. JSONL input/output. No SysEx.")
    exit(0)
}
guard args.isEmpty else { emit("error", ["message": "Unknown arguments; use --help"]); exit(2) }
private let transport = Transport()
guard transport.start() else { exit(1) }
transport.installSignals()
DispatchQueue.global(qos: .userInitiated).async {
    while let line = readLine() { transport.accept(line) }
    transport.endOfInput()
}
dispatchMain()
