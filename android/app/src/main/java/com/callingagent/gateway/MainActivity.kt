package com.callingagent.gateway

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

/**
 * MainActivity — Simple UI to configure the backend server URL and start/stop the gateway service.
 *
 * Usage:
 *   1. Enter backend IP:port (e.g. ws://192.168.1.100:8765).
 *   2. Tap "Connect".  The GatewayService starts and connects to the Python backend.
 *   3. The Python backend now controls all calls remotely.
 *   4. Tap "Disconnect" to shut down the gateway.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val PERM_REQUEST_CODE = 42
        private val REQUIRED_PERMISSIONS = arrayOf(
            Manifest.permission.CALL_PHONE,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.READ_PHONE_STATE,
        )
    }

    private lateinit var urlInput: EditText
    private lateinit var connectBtn: Button
    private lateinit var statusText: TextView
    private var serviceRunning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        urlInput   = findViewById(R.id.urlInput)
        connectBtn = findViewById(R.id.connectBtn)
        statusText = findViewById(R.id.statusText)

        connectBtn.setOnClickListener {
            if (serviceRunning) stopGateway() else startGateway()
        }

        requestPermissionsIfNeeded()
    }

    private fun startGateway() {
        val url = urlInput.text.toString().trim().ifEmpty { "ws://192.168.1.100:8765" }
        val intent = Intent(this, GatewayService::class.java).apply {
            putExtra("server_url", url)
        }
        ContextCompat.startForegroundService(this, intent)
        serviceRunning = true
        connectBtn.text = "Disconnect"
        statusText.text = "Connected to $url"
    }

    private fun stopGateway() {
        stopService(Intent(this, GatewayService::class.java))
        serviceRunning = false
        connectBtn.text = "Connect"
        statusText.text = "Disconnected"
    }

    private fun requestPermissionsIfNeeded() {
        val missing = REQUIRED_PERMISSIONS.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), PERM_REQUEST_CODE)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERM_REQUEST_CODE) {
            val allGranted = grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            statusText.text = if (allGranted) "Permissions granted ✓" else "⚠ Some permissions denied"
        }
    }
}
