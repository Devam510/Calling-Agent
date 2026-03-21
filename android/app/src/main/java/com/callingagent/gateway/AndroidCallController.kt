package com.callingagent.gateway

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.telecom.TelecomManager
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

private const val TAG = "AndroidCallController"

/**
 * Wraps TelecomManager to dial and hang up calls.
 * Notifies GatewayService of state changes via sendCallState().
 */
class AndroidCallController(private val context: Context) {

    private val telecomManager =
        context.getSystemService(Context.TELECOM_SERVICE) as TelecomManager
    private val scope = CoroutineScope(Dispatchers.IO)

    /**
     * Dial a phone number using the default dialer.
     * The app must be set as the default dialer for this to work.
     */
    fun dial(phone: String) {
        val uri = android.net.Uri.parse("tel:${phone}")
        telecomManager.placeCall(uri, null)
        Log.i(TAG, "Dialing $phone")
    }

    /**
     * Hang up the current active call.
     * Uses endCall() — requires CALL_PHONE permission.
     */
    fun hangUp() {
        @Suppress("DEPRECATION")
        telecomManager.endCall()
        Log.i(TAG, "Call ended")
    }

    /**
     * Send DTMF tones — done via InCallService.
     * The active call object exposes sendDtmfTone().
     * DTMF is sent via CallService (see CallService.kt).
     */
    fun sendDtmf(digits: String) {
        CallService.currentCall?.let { call ->
            digits.forEach { digit ->
                call.sendDtmfTone(digit)
                Log.d(TAG, "Sent DTMF: $digit")
            }
        } ?: Log.w(TAG, "No active call for DTMF: $digits")
    }
}
