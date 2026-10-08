import NetworkExtension
import os.log

/**
 * PacketTunnelProvider: Apple NetworkExtension Tunnel implementation.
 * Transparently bridges outbound mobile packets into the local NexusProxy Rust engine.
 */
class PacketTunnelProvider: NEPacketTunnelProvider {

    private let log = OSLog(subsystem: "com.nexusproxy.mobile", category: "Tunnel")

    override func startTunnel(options: [String : NSObject]?, completionHandler: @escaping (Error?) -> Void) {
        os_log("Starting NexusProxy iOS Packet Tunnel...", log: self.log, type: .info)

        let tunnelNetworkSettings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: "127.0.0.1")
        
        let ipv4Settings = NEIPv4Settings(addresses: ["10.0.0.3"], subnetMasks: ["255.255.255.0"])
        ipv4Settings.includedRoutes = [NEIPv4Route.default()]
        tunnelNetworkSettings.ipv4Settings = ipv4Settings

        // Configure Local DNS
        tunnelNetworkSettings.dnsSettings = NEDNSSettings(servers: ["1.1.1.1", "8.8.8.8"])

        setTunnelNetworkSettings(tunnelNetworkSettings) { error in
            if let error = error {
                os_log("Failed to set tunnel settings: %{public}@", log: self.log, type: .error, error.localizedDescription)
                completionHandler(error)
                return
            }

            os_log("NexusProxy iOS Tunnel Armed successfully.", log: self.log, type: .info)
            completionHandler(nil)
        }
    }

    override func stopTunnel(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
        os_log("Stopping NexusProxy iOS Packet Tunnel...", log: self.log, type: .info)
        completionHandler()
    }
}
