package org.lightning.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;
import com.chaquo.python.Python;
import java.io.ByteArrayInputStream;

/** Lightning on the phone: the shared pages in a WebView locked to this phone's own server (task 04c rules). */
public final class MainActivity extends Activity {
    private WebView web;
    private Uri origin;
    private boolean openSms;  // a message was shared in before the pages were ready

    static void fitSystemBars(View view) {
        if (Build.VERSION.SDK_INT >= 30) {
            view.setOnApplyWindowInsetsListener((v, insets) -> {
                Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime()
                        | WindowInsets.Type.displayCutout());
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return WindowInsets.CONSUMED;
            });
        } else {
            view.setFitsSystemWindows(true);
        }
    }

    private boolean ours(Uri uri) {
        return origin != null && "http".equals(uri.getScheme()) && origin.getHost().equals(uri.getHost())
                && origin.getPort() == uri.getPort();
    }

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        SmsBridge.activity = this;
        takeShare(getIntent());
        WebView.setWebContentsDebuggingEnabled(false);
        FrameLayout frame = new FrameLayout(this);
        fitSystemBars(frame);
        TextView starting = new TextView(this);
        starting.setPadding(48, 48, 48, 48);
        starting.setText("Starting Lightning…");
        frame.addView(starting);
        setContentView(frame);
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
        }
        String files = getFilesDir().getAbsolutePath();
        new Thread(() -> {
            try {
                String url = Python.getInstance().getModule("lightning_android").callAttr("start", files).toString();
                runOnUiThread(() -> show(frame, url));
            } catch (Throwable error) {
                String text = "Lightning could not start:\n" + Log.getStackTraceString(error);
                runOnUiThread(() -> {
                    starting.setText(text);
                    starting.setTextIsSelectable(true);
                });
            }
        }, "lightning-start").start();
    }

    private void show(FrameLayout frame, String url) {
        origin = Uri.parse(url);
        web = new WebView(this);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setSupportMultipleWindows(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setGeolocationEnabled(false);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !ours(request.getUrl());  // another site, a file or an app link: never opened
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                if (ours(request.getUrl())) return null;
                return new WebResourceResponse("text/plain", "utf-8", 403, "Forbidden", null,
                        new ByteArrayInputStream(new byte[0]));
            }
        });
        frame.removeAllViews();
        frame.addView(web);
        web.loadUrl(url);
        if (openSms) {
            openSms = false;
            web.postDelayed(() -> web.loadUrl(origin.buildUpon().path("/sms").build().toString()), 1500);
        }
    }

    /** "Share" from the SMS app: the text waits for the Python side, and From SMS opens to read it. */
    private void takeShare(Intent intent) {
        if (intent == null || !Intent.ACTION_SEND.equals(intent.getAction())) return;
        CharSequence text = intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
        if (text == null) return;
        SmsBridge.share(text.toString());
        if (web != null && origin != null) web.loadUrl(origin.buildUpon().path("/sms").build().toString());
        else openSms = true;
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        takeShare(intent);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == SmsBridge.REQUEST_SMS && web != null && origin != null) {
            web.loadUrl(origin.buildUpon().path("/sms").build().toString());  // read right away, or say why not
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else moveTaskToBack(true);  // keep the server and an open lend reachable
    }

    @Override
    protected void onStart() {
        super.onStart();
        stopService(new Intent(this, SyncService.class));
    }

    @Override
    protected void onStop() {
        super.onStop();
        new Thread(() -> {
            try {
                String note = Python.getInstance().getModule("lightning_android").callAttr("background_note").toString();
                if (!note.isEmpty()) {
                    Intent intent = new Intent(this, SyncService.class).putExtra("note", note);
                    if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
                    else startService(intent);
                }
            } catch (Throwable ignored) {
                // Without the service the PC hands back the next time Lightning is open here.
            }
        }, "lightning-background").start();
    }
}
