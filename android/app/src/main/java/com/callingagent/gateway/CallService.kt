package com.callingagent.gateway

import android.telecom.Call
import android.telecom.InCallService
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

private const val TAG = "CallService"

/**
 * InCallService — receives call state events from the system.
 *
 * The system routes call events here when the app is the default dialer.
 * We forward call state (ringing, connected, ended) to GatewayService
 * via the shared GatewayService reference.
 */
class CallService : InCallService() {

    companion object {
        @Volatile var currentCall: Call? = null
            private set
    }

    private val scope = CoroutineScope(Dispatchers.IO)

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        currentCall = call
        Log.i(TAG, "Call added: state=${call.state}")

        call.registerCallback(object : Call.Callback() {
            override fun onStateChanged(call: Call, state: Int) {
                Log.i(TAG, "Call state changed: $state")
                scope.launch {
                    when (state) {
                        Call.STATE_RINGING    -> notifyState("ringing")
                        Call.STATE_ACTIVE     -> notifyState("connected")
                        Call.STATE_DISCONNECTED -> {
                            notifyState("ended")
                            currentCall = null
                        }
                        Call.STATE_DIALING    -> notifyState("dialing")
                        Call.STATE_CONNECTING -> notifyState("connecting")
                        else -> { /* ignore other states */ }
                    }
                }
            }
        })
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        currentCall = null
        scope.launch { notifyState("ended") }
        Log.i(TAG, "Call removed")
    }

    private suspend fun notifyState(state: String) {
        // GatewayService is a singleton Service — we can access it via startService context trick
        // Instead we use a global accessor via Application or broadcast
        GatewayServiceHolder.instance?.sendCallState(state)
    }
}

/**
 * Simple singleton holder for GatewayService reference.
 * Set in GatewayService.onStartCommand, cleared in onDestroy.
 */
object GatewayServiceHolder {
    @Volatile var instance: GatewayService? = null
}
