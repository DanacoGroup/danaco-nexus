package pl.danaco.nexus.web

import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import com.getcapacitor.Bridge
import com.getcapacitor.BridgeWebViewClient
import pl.danaco.nexus.config.NexusConfig

/**
 * Klient WebView okna głównego. Żądania do Nexusa idą prosto do sieci (bez pośrednika Capacitor,
 * który podmienia nagłówki odpowiedzi HTML, m.in. CSP) – mostek aplikacji wstrzykuje
 * `addDocumentStartJavaScript`. Lokalne pliki Capacitor (strona błędu) obsługuje klasa bazowa.
 */
class NexusWebViewClient(private val bridge: Bridge) : BridgeWebViewClient(bridge) {
    override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
        if (NexusConfig.isNexusHost(request.url.host)) return null
        return super.shouldInterceptRequest(view, request)
    }

    override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, errorResponse: WebResourceResponse) {
        // Strona „brak połączenia” tylko dla błędów serwera; 404 itp. pokazuje sama aplikacja.
        if (errorResponse.statusCode >= 500) {
            super.onReceivedHttpError(view, request, errorResponse)
        }
    }
}
