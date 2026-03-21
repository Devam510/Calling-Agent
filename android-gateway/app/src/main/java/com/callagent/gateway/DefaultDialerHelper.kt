// android-gateway/app/src/main/java/com/callagent/gateway/DefaultDialerHelper.kt
package com.callagent.gateway

import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

class DefaultDialerHelper(private val activity: AppCompatActivity) {
    private val roleManager = activity.getSystemService(Context.ROLE_SERVICE) as RoleManager

    private val requestRoleLauncher = activity.registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (roleManager.isRoleHeld(RoleManager.ROLE_DIALER)) {
            // Success
        }
    }

    fun requestDefaultDialerRole() {
        if (!roleManager.isRoleHeld(RoleManager.ROLE_DIALER)) {
            val intent = roleManager.createRequestRoleIntent(RoleManager.ROLE_DIALER)
            requestRoleLauncher.launch(intent)
        }
    }
}
