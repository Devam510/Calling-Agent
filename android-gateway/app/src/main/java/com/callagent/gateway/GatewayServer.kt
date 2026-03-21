// android-gateway/app/src/main/java/com/callagent/gateway/GatewayServer.kt
package com.callagent.gateway

// Note: Requires Ktor dependencies, Coroutines
import io.ktor.server.application.*
import io.ktor.server.engine.*
import io.ktor.server.netty.*
import io.ktor.server.routing.*
import io.ktor.server.websocket.*
import io.ktor.websocket.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.util.concurrent.CopyOnWriteArrayList

object GatewayServer {
    private val connections = CopyOnWriteArrayList<DefaultWebSocketServerSession>()

    fun start() {
        CoroutineScope(Dispatchers.IO).launch {
            embeddedServer(Netty, port = 8765) {
                install(WebSockets)

                routing {
                    webSocket("/") {
                        connections.add(this)
                        try {
                            for (frame in incoming) {
                                if (frame is Frame.Text) {
                                    handleCommand(frame.readText())
                                } else if (frame is Frame.Binary) {
                                    // Received audio from Python backend, play it through earpiece/speaker
                                    // AudioPlayer.play(frame.readBytes())
                                }
                            }
                        } catch (e: Exception) {
                            e.printStackTrace()
                        } finally {
                            connections.remove(this)
                        }
                    }
                }
            }.start(wait = true)
        }
    }

    private fun handleCommand(cmd: String) {
        val json = JSONObject(cmd)
        when (json.getString("type")) {
            "START_CALL" -> {
                val number = json.getString("number")
                // Start call flow via TelecomManager context
            }
            "END_CALL" -> {
                // Terminate call flow
            }
        }
    }

    fun broadcastStatus(status: String) {
        val payload = """{"type": "CALL_STATUS", "status": "$status"}"""
        CoroutineScope(Dispatchers.IO).launch {
            for (conn in connections) {
                conn.send(Frame.Text(payload))
            }
        }
    }

    fun broadcastAudio(data: ByteArray) {
        CoroutineScope(Dispatchers.IO).launch {
            for (conn in connections) {
                conn.send(Frame.Binary(true, data))
            }
        }
    }
}
