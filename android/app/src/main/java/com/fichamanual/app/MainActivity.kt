package com.fichamanual.app

import android.content.ClipData
import android.content.ClipboardManager
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import com.fichamanual.app.databinding.ActivityMainBinding
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnSummarize.setOnClickListener { createFicha() }
        binding.btnClear.setOnClickListener { clearAll() }
        binding.btnCopy.setOnClickListener { copyFicha() }
    }

    private fun createFicha() {
        val input = binding.inputText.text?.toString().orEmpty()
        if (input.isBlank()) {
            Toast.makeText(this, R.string.empty_input, Toast.LENGTH_SHORT).show()
            return
        }
        setBusy(true)
        thread {
            val result = runCatching { Summarizer.summarize(input) }
                .getOrElse { "Error al resumir: ${it.message}" }
            runOnUiThread {
                binding.outputText.setText(result)
                setBusy(false)
            }
        }
    }

    private fun clearAll() {
        binding.inputText.setText("")
        binding.outputText.setText("")
    }

    private fun copyFicha() {
        val text = binding.outputText.text?.toString().orEmpty()
        if (text.isBlank()) {
            Toast.makeText(this, R.string.empty_output, Toast.LENGTH_SHORT).show()
            return
        }
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("FichaManual", text))
        Toast.makeText(this, R.string.copied, Toast.LENGTH_SHORT).show()
    }

    private fun setBusy(busy: Boolean) {
        binding.progress.isVisible = busy
        binding.btnSummarize.isEnabled = !busy
        binding.btnClear.isEnabled = !busy
        binding.btnCopy.isEnabled = !busy
        binding.inputText.isEnabled = !busy
    }
}
