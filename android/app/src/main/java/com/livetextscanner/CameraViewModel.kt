package com.livetextscanner

import android.graphics.RectF
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class DetectedBlock(
    val text: String,
    val boundingBox: RectF
)

class CameraViewModel : ViewModel() {

    private val _detectedBlocks = MutableStateFlow<List<DetectedBlock>>(emptyList())
    val detectedBlocks: StateFlow<List<DetectedBlock>> = _detectedBlocks.asStateFlow()

    private val _concatenatedText = MutableStateFlow("")
    val concatenatedText: StateFlow<String> = _concatenatedText.asStateFlow()

    private val _isProcessing = MutableStateFlow(false)
    val isProcessing: StateFlow<Boolean> = _isProcessing.asStateFlow()

    private val _isModelReady = MutableStateFlow(false)
    val isModelReady: StateFlow<Boolean> = _isModelReady.asStateFlow()

    private val _flashOverlay = MutableStateFlow(false)
    val flashOverlay: StateFlow<Boolean> = _flashOverlay.asStateFlow()

    private val _textDetected = MutableStateFlow(false)
    val textDetected: StateFlow<Boolean> = _textDetected.asStateFlow()

    var lensFacing = 0

    fun updateDetectedText(
        blocks: List<DetectedBlock>,
        allText: String
    ) {
        _detectedBlocks.value = blocks
        _concatenatedText.value = allText
        _textDetected.value = blocks.isNotEmpty()
        _isProcessing.value = false
    }

    fun clearDetectedText() {
        _detectedBlocks.value = emptyList()
        _concatenatedText.value = ""
        _textDetected.value = false
        _isProcessing.value = false
    }

    fun setProcessing(processing: Boolean) {
        _isProcessing.value = processing
    }

    fun setModelReady(ready: Boolean) {
        _isModelReady.value = ready
    }

    fun triggerFlash() {
        _flashOverlay.value = true
    }

    fun clearFlash() {
        _flashOverlay.value = false
    }
}
