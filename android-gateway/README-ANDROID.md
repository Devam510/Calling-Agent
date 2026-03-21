# Android Call Gateway

This directory contains the essential Kotlin files to build the Android Call Gateway.
The app acts as the Default Dialer to intercept calls and capture/inject audio.
It exposes a WebSocket server on port `8765` so the Python backend can coordinate with it.

## How to build
1. Open Android Studio and create a new **Empty Activity** project (Kotlin).
2. Set the package name to `com.callagent.gateway`.
3. Copy the files in `app/src/main/java/com/callagent/gateway` to your project's corresponding directory.
4. Open your `app/build.gradle` (or `build.gradle.kts`) and add the Ktor dependencies for the WebSocket Server:
   ```kotlin
   implementation("io.ktor:ktor-server-core:2.3.4")
   implementation("io.ktor:ktor-server-netty:2.3.4")
   implementation("io.ktor:ktor-server-websockets:2.3.4")
   ```
5. Update your `AndroidManifest.xml` to declare the permissions and the `InCallService`:
   ```xml
   <uses-permission android:name="android.permission.RECORD_AUDIO" />
   <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
   <uses-permission android:name="android.permission.CALL_PHONE" />
   <uses-permission android:name="android.permission.READ_PHONE_STATE" />
   <uses-permission android:name="android.permission.INTERNET" />
   
   <application>
       <!-- Activity declarations... -->

       <service android:name=".CallService"
                android:permission="android.permission.BIND_INCALL_SERVICE"
                android:exported="true">
           <meta-data android:name="android.telecom.IN_CALL_SERVICE_UI" android:value="true" />
           <intent-filter>
               <action android:name="android.telecom.InCallService"/>
           </intent-filter>
       </service>
   </application>
   ```

## Usage
1. Connect your Android device via USB or ensure it is on the same Wi-Fi network.
2. Build and run the App on your device.
3. Tap **Set as Default Dialer** to grant it the authority to handle phone calls.
4. Tap **Start Gateway Server** to launch the WebSocket server.
5. Note the device's IP Address and connect your Python backend to `ws://<DEVICE_IP>:8765`.
