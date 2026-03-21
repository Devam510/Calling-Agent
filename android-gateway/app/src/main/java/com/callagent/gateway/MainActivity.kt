// android-gateway/app/src/main/java/com/callagent/gateway/MainActivity.kt
package com.callagent.gateway

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {
    private val defaultDialerHelper = DefaultDialerHelper(this)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        requestPermissions()

        val btnSetDialer = findViewById<Button>(R.id.btnSetDialer)
        btnSetDialer.setOnClickListener {
            defaultDialerHelper.requestDefaultDialerRole()
        }

        val btnStartServer = findViewById<Button>(R.id.btnStartServer)
        btnStartServer.setOnClickListener {
            GatewayServer.start()
            Toast.makeText(this, "WebSocket Gateway Started on 8765", Toast.LENGTH_SHORT).show()
        }
    }

    private fun requestPermissions() {
        val permissions = arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CALL_PHONE,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.INTERNET,
            Manifest.permission.MODIFY_AUDIO_SETTINGS
        )

        val needed = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), 100)
        }
    }
}
