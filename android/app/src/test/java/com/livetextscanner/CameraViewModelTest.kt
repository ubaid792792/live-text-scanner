package com.livetextscanner

import android.graphics.RectF
import androidx.arch.core.executor.testing.InstantTaskExecutorRule
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class CameraViewModelTest {

    @get:Rule
    val instantRule = InstantTaskExecutorRule()

    private fun createViewModel() = CameraViewModel()

    @Test
    fun `initial state has empty blocks and no text`() = runBlocking {
        val vm = createViewModel()
        assertTrue(vm.detectedBlocks.first().isEmpty())
        assertEquals("", vm.concatenatedText.first())
        assertFalse(vm.isProcessing.first())
        assertFalse(vm.isModelReady.first())
        assertFalse(vm.flashOverlay.first())
        assertFalse(vm.textDetected.first())
    }

    @Test
    fun `updateDetectedText sets blocks and concatenated text`() = runBlocking {
        val vm = createViewModel()
        val blocks = listOf(
            DetectedBlock("Hello", RectF(10f, 20f, 100f, 50f)),
            DetectedBlock("World", RectF(10f, 60f, 120f, 90f))
        )
        vm.updateDetectedText(blocks, "Hello\nWorld")

        assertEquals(2, vm.detectedBlocks.first().size)
        assertEquals("Hello", vm.detectedBlocks.first()[0].text)
        assertEquals("World", vm.detectedBlocks.first()[1].text)
        assertEquals("Hello\nWorld", vm.concatenatedText.first())
        assertTrue(vm.textDetected.first())
        assertFalse(vm.isProcessing.first())
    }

    @Test
    fun `updateDetectedText with empty blocks sets textDetected to false`() = runBlocking {
        val vm = createViewModel()
        vm.updateDetectedText(emptyList(), "")
        assertFalse(vm.textDetected.first())
        assertEquals("", vm.concatenatedText.first())
    }

    @Test
    fun `clearDetectedText resets all text state`() = runBlocking {
        val vm = createViewModel()
        vm.updateDetectedText(
            listOf(DetectedBlock("Hi", RectF(0f, 0f, 10f, 10f))),
            "Hi"
        )
        vm.clearDetectedText()

        assertTrue(vm.detectedBlocks.first().isEmpty())
        assertEquals("", vm.concatenatedText.first())
        assertFalse(vm.textDetected.first())
        assertFalse(vm.isProcessing.first())
    }

    @Test
    fun `setProcessing toggles processing state`() = runBlocking {
        val vm = createViewModel()
        vm.setProcessing(true)
        assertTrue(vm.isProcessing.first())
        vm.setProcessing(false)
        assertFalse(vm.isProcessing.first())
    }

    @Test
    fun `setModelReady toggles model ready state`() = runBlocking {
        val vm = createViewModel()
        assertFalse(vm.isModelReady.first())

        vm.setModelReady(true)
        assertTrue(vm.isModelReady.first())

        vm.setModelReady(false)
        assertFalse(vm.isModelReady.first())
    }

    @Test
    fun `triggerFlash sets flashOverlay to true`() = runBlocking {
        val vm = createViewModel()
        vm.triggerFlash()
        assertTrue(vm.flashOverlay.first())
    }

    @Test
    fun `clearFlash sets flashOverlay to false`() = runBlocking {
        val vm = createViewModel()
        vm.triggerFlash()
        vm.clearFlash()
        assertFalse(vm.flashOverlay.first())
    }

    @Test
    fun `lensFacing defaults to back camera (0)`() {
        val vm = createViewModel()
        assertEquals(0, vm.lensFacing)
    }

    @Test
    fun `updateDetectedText clears isProcessing flag`() = runBlocking {
        val vm = createViewModel()
        vm.setProcessing(true)
        assertTrue(vm.isProcessing.first())

        vm.updateDetectedText(
            listOf(DetectedBlock("test", RectF(1f, 2f, 3f, 4f))),
            "test"
        )
        assertFalse(vm.isProcessing.first())
    }

    @Test
    fun `multiple rapid updates keep latest state`() = runBlocking {
        val vm = createViewModel()

        vm.updateDetectedText(
            listOf(DetectedBlock("A", RectF(0f, 0f, 1f, 1f))),
            "A"
        )
        assertEquals("A", vm.concatenatedText.first())

        vm.updateDetectedText(
            listOf(DetectedBlock("B", RectF(0f, 0f, 1f, 1f))),
            "B"
        )
        assertEquals("B", vm.concatenatedText.first())

        vm.clearDetectedText()
        assertEquals("", vm.concatenatedText.first())
    }
}
