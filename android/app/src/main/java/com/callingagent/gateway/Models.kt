package com.callingagent.gateway

/**
 * Sealed hierarchy for commands received FROM the Python backend.
 */
sealed interface GatewayCommand {
    /** Backend wants to initiate a call to this number. */
    data class StartCall(val phoneNumber: String) : GatewayCommand

    /** Backend wants to end the active call. */
    object EndCall : GatewayCommand

    /** Backend acknowledges the call is connected — start audio capture. */
    object CallConnected : GatewayCommand

    /** TTS audio chunk (raw PCM) to be played on the device. */
    data class AudioOut(val pcmData: ByteArray) : GatewayCommand
}

/**
 * Sealed hierarchy for events sent TO the Python backend.
 */
sealed interface GatewayEvent {
    data class CallStateChanged(val state: String) : GatewayEvent
    data class Error(val message: String) : GatewayEvent
    object Ringing : GatewayEvent
    object Connected : GatewayEvent
    object Disconnected : GatewayEvent
}
