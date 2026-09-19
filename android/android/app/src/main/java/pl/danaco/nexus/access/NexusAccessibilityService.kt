package pl.danaco.nexus.access

import android.accessibilityservice.AccessibilityService
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import pl.danaco.nexus.assist.ScreenContent
import pl.danaco.nexus.assist.TextCollector

/**
 * Opcjonalna usługa dostępności (włączana ręcznie w ustawieniach systemu): na żądanie użytkownika
 * czyta tekst aplikacji pod panelem Nexusa i wstawia odpowiedź w jej aktywne pole. Nie reaguje na
 * zdarzenia w tle, niczego nie wysyła i nie klika przycisków – tylko ustawia tekst pola.
 */
class NexusAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        if (instance === this) instance = null
        super.onDestroy()
    }

    /** Okno aplikacji pod nakładką Nexusa (pomija okna systemowe i własne okna Nexusa). */
    private fun appRoot(): AccessibilityNodeInfo? {
        val own = packageName
        val candidates = windows
            .filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
            .sortedByDescending { it.layer }
        for (window in candidates) {
            val root = window.root ?: continue
            if (root.packageName?.toString() != own) return root
        }
        return rootInActiveWindow?.takeIf { it.packageName?.toString() != own }
    }

    /** Tekst i nazwa pakietu aplikacji na ekranie. */
    fun readScreen(limit: Int = 12_000): Pair<String, String>? {
        val root = appRoot() ?: return null
        val collector = TextCollector(limit)
        walk(root, collector)
        return (root.packageName?.toString().orEmpty()) to collector.text()
    }

    private fun walk(node: AccessibilityNodeInfo?, collector: TextCollector) {
        if (node == null || collector.full || !node.isVisibleToUser) return
        if (!node.isPassword && !ScreenContent.isPassword(node.inputType)) {
            collector.add(node.text)
            if (node.text.isNullOrBlank()) collector.add(node.contentDescription)
        }
        for (index in 0 until node.childCount) walk(node.getChild(index), collector)
    }

    /** Wstawia tekst w aktywne pole edycji (dopisuje do istniejącej treści). */
    fun insertIntoFocused(text: String): Boolean {
        val root = appRoot() ?: return false
        val field = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)?.takeIf { it.isEditable && !it.isPassword }
            ?: findEditable(root)
            ?: return false
        val current = field.text?.toString().orEmpty().takeUnless { field.isShowingHintText }.orEmpty()
        val value = if (current.isBlank()) text else current.trimEnd() + " " + text
        val arguments = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value)
        }
        return field.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)
    }

    private fun findEditable(node: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        if (node == null) return null
        if (node.isEditable && node.isVisibleToUser && !node.isPassword) return node
        for (index in 0 until node.childCount) findEditable(node.getChild(index))?.let { return it }
        return null
    }

    companion object {
        @Volatile
        var instance: NexusAccessibilityService? = null
            private set
    }
}
