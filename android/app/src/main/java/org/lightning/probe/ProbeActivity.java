package org.lightning.probe;

import android.app.Activity;
import android.os.Bundle;
import android.widget.ScrollView;
import android.widget.TextView;
import com.chaquo.python.Python;

public final class ProbeActivity extends Activity {
    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView result = new TextView(this);
        result.setPadding(32, 160, 32, 32);  // below the status bar
        result.setTextIsSelectable(true);
        try {
            result.setText(Python.getInstance().getModule("probe").callAttr("run").toString());
        } catch (Exception error) {
            result.setText("Dependency probe failed: " + error);  // the Python error and its message
        }
        ScrollView scroll = new ScrollView(this);
        scroll.addView(result);
        setContentView(scroll);
    }
}
