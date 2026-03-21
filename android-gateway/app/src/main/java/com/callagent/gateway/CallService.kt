// android-gateway/app/src/main/java/com/callagent/gateway/CallService.kt
package com.callagent.gateway

import android.telecom.Call
import android.telecom.InCallService
import android.util.Log

class CallService : InCallService() {
    companion object {
        var activeCall: Call? = null
    }

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        Log.i("CallService", "Call added: ${call.details.handle}")
        activeCall = call

        call.registerCallback(object : Call.Callback() {
            override fun onStateChanged(call: Call, state: Int) {
                super.onStateChanged(call, state)
                if (state == Call.STATE_DISCONNECTED) {
                    activeCall = null
                    GatewayServer.broadcastStatus("DISCONNECTED")
                } else if (state == Call.STATE_ACTIVE) {
                    GatewayServer.broadcastStatus("CONNECTED")
                    // In a real app, start audio capture/injection here
                    AudioCapture.startCapture()
                }
            }
        })
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        Log.i("CallService", "Call removed")
        if (activeCall == call) {
            activeCall = null
        }
    }

    fun endCall() {
        activeCall?.disconnect()
    }
}
