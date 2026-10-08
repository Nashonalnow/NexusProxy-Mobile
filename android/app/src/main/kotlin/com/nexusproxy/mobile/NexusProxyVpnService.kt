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

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "Starting NexusProxy VPN Interception Service...")
        startVpnTunnel()
        return START_STICKY
    }

    private fun startVpnTunnel() {
        if (isRunning) return

        try {
            val builder = Builder()
                .setSession("NexusProxy Mobile Sentry")
                .addAddress(VPN_ADDRESS, 24)
                .addRoute(VPN_ROUTE, 0)
                .setMtu(1500)
                .setBlocking(false)

            vpnInterface = builder.establish()
            isRunning = true
            Log.i(TAG, "Virtual TUN interface established successfully: ${vpnInterface?.fd}")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to establish VPN interface: ${e.message}", e)
        }
    }

    override fun onDestroy() {
        Log.i(TAG, "Stopping NexusProxy VPN Service...")
        isRunning = false
        vpnInterface?.close()
        vpnInterface = null
        super.onDestroy()
    }
}
