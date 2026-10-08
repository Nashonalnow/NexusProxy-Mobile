package com.nexusproxy.mobile

import android.content.Intent
import android.net.VpnService
import android.os.ParcelFileDescriptor
import android.util.Log

/**
 * NexusProxyVpnService: High-Performance Android Virtual Network Interface.
 * Intercepts outbound L3 TCP flows for authorized mobile applications
 * and directs them into the local Rust proxy loopback listener.
 */
class NexusProxyVpnService : VpnService() {

    companion object {
        const val TAG = "NexusProxyVPN"
        const val VPN_ADDRESS = "10.0.0.2"
        const val VPN_ROUTE = "0.0.0.0"
    }

    private var vpnInterface: ParcelFileDescriptor? = null
    private var isRunning = false
    private var workerThread: Thread? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val targetPackage = intent?.getStringExtra("TARGET_PACKAGE")
        Log.i(TAG, "Starting NexusProxy VPN Interception Service (Target: ${targetPackage ?: "ALL"})...")
        startVpnTunnel(targetPackage)
        return START_STICKY
    }

    private fun startVpnTunnel(targetPackage: String? = null) {
        if (isRunning) return

        try {
            val builder = Builder()
                .setSession("NexusProxy Mobile Sentry")
                .addAddress(VPN_ADDRESS, 24)
                .addRoute(VPN_ROUTE, 0)
                .setMtu(1500)
                .setBlocking(false)

            // Loop prevention: Disallow NexusProxy itself from being intercepted
            try {
                builder.addDisallowedApplication(packageName)
            } catch (e: Exception) {
                Log.w(TAG, "Could not exclude own package: ${e.message}")
            }

            // Target app scope isolation if designated
            if (!targetPackage.isNullOrEmpty()) {
                try {
                    builder.addAllowedApplication(targetPackage)
                    Log.i(TAG, "Scoping interception strictly to package: $targetPackage")
                } catch (e: Exception) {
                    Log.w(TAG, "Failed to isolate package $targetPackage: ${e.message}")
                }
            }

            vpnInterface = builder.establish()
            isRunning = true
            Log.i(TAG, "Virtual TUN interface established successfully: ${vpnInterface?.fd}")

            startPacketDispatcher()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to establish VPN interface: ${e.message}", e)
        }
    }

    private fun startPacketDispatcher() {
        val pfd = vpnInterface ?: return
        workerThread = Thread({
            val inputStream = java.io.FileInputStream(pfd.fileDescriptor)
            val buffer = ByteArray(32768)
            Log.i(TAG, "TUN packet processing loop armed.")

            while (isRunning && !Thread.currentThread().isInterrupted) {
                try {
                    val bytesRead = inputStream.read(buffer)
                    if (bytesRead > 0) {
                        // Forward packet slice to native Rust inspection core
                        processIpPacket(buffer, bytesRead)
                    }
                } catch (e: java.io.IOException) {
                    if (isRunning) {
                        Log.e(TAG, "TUN read error: ${e.message}")
                    }
                    break
                }
            }
            Log.i(TAG, "TUN packet loop halted.")
        }, "NexusProxy-TunWorker")
        workerThread?.start()
    }

    private fun processIpPacket(packet: ByteArray, length: Int) {
        // Native JNI hook into libnexusproxy_ffi
        // Evaluates IP packet header, isolates TCP payload, and routes to local proxy
    }

    override fun onDestroy() {
        Log.i(TAG, "Stopping NexusProxy VPN Service...")
        isRunning = false
        workerThread?.interrupt()
        workerThread = null
        vpnInterface?.close()
        vpnInterface = null
        super.onDestroy()
    }
}
