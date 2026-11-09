package com.livetextscanner

import android.graphics.Rect
import android.graphics.RectF
import org.junit.Assert.*
import org.junit.Test

class CoordinateTransformerTest {

    private val imgW = 1920
    private val imgH = 1080
    private val viewW = 1440
    private val viewH = 810

    @Test
    fun `no rotation no mirror maps directly scaled`() {
        val rect = Rect(100, 200, 500, 400)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 0, isFrontCamera = false
        )

        val expectedLeft = 100f / imgW * viewW
        val expectedTop = 200f / imgH * viewH
        val expectedRight = 500f / imgW * viewW
        val expectedBottom = 400f / imgH * viewH

        assertEquals(expectedLeft, result.left, 0.01f)
        assertEquals(expectedTop, result.top, 0.01f)
        assertEquals(expectedRight, result.right, 0.01f)
        assertEquals(expectedBottom, result.bottom, 0.01f)
    }

    @Test
    fun `rotation 90 swaps coordinates`() {
        val rect = Rect(0, 0, imgW, imgH)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 90, isFrontCamera = false
        )

        assertEquals(0f, result.left, 0.01f)
        assertEquals(0f, result.top, 0.01f)
        assertEquals(viewW.toFloat(), result.right, 0.01f)
        assertEquals(viewH.toFloat(), result.bottom, 0.01f)
    }

    @Test
    fun `rotation 180 inverts both axes`() {
        val rect = Rect(100, 200, 500, 400)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 180, isFrontCamera = false
        )

        val expectedLeft = (1f - 500f / imgW) * viewW
        val expectedTop = (1f - 400f / imgH) * viewH
        val expectedRight = (1f - 100f / imgW) * viewW
        val expectedBottom = (1f - 200f / imgH) * viewH

        assertEquals(expectedLeft, result.left, 0.01f)
        assertEquals(expectedTop, result.top, 0.01f)
        assertEquals(expectedRight, result.right, 0.01f)
        assertEquals(expectedBottom, result.bottom, 0.01f)
    }

    @Test
    fun `rotation 270 inverts axes swapped`() {
        val rect = Rect(0, 0, imgW, imgH)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 270, isFrontCamera = false
        )

        assertEquals(0f, result.left, 0.01f)
        assertEquals(0f, result.top, 0.01f)
        assertEquals(viewW.toFloat(), result.right, 0.01f)
        assertEquals(viewH.toFloat(), result.bottom, 0.01f)
    }

    @Test
    fun `front camera mirrors x-axis with no rotation`() {
        val rect = Rect(0, 0, imgW, imgH)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 0, isFrontCamera = true
        )

        assertEquals(0f, result.left, 0.01f)
        assertEquals(0f, result.top, 0.01f)
        assertEquals(viewW.toFloat(), result.right, 0.01f)
        assertEquals(viewH.toFloat(), result.bottom, 0.01f)
    }

    @Test
    fun `front camera mirror with small rect`() {
        val rect = Rect(100, 200, 500, 400)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 0, isFrontCamera = true
        )

        val mirroredLeft = (1f - 500f / imgW) * viewW
        val mirroredRight = (1f - 100f / imgW) * viewW

        assertEquals(mirroredLeft, result.left, 0.01f)
        assertEquals(mirroredRight, result.right, 0.01f)
    }

    @Test
    fun `small rect in center stays centered`() {
        val rect = Rect(860, 440, 1060, 640)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 0, isFrontCamera = false
        )

        val cx = (rect.left + rect.right) / 2f / imgW * viewW
        val cy = (rect.top + rect.bottom) / 2f / imgH * viewH

        val resultCx = (result.left + result.right) / 2f
        val resultCy = (result.top + result.bottom) / 2f

        assertEquals(cx, resultCx, 1f)
        assertEquals(cy, resultCy, 1f)
    }

    @Test
    fun `results clamped to view bounds for full-frame rect`() {
        val rect = Rect(-50, -50, imgW + 50, imgH + 50)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 0, isFrontCamera = false
        )

        assertTrue(result.left <= result.right)
        assertTrue(result.top <= result.bottom)
        assertTrue(result.right >= 0f)
        assertTrue(result.bottom >= 0f)
    }

    @Test
    fun `zero-size rect produces zero-size output`() {
        val rect = Rect(500, 400, 500, 400)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 0, isFrontCamera = false
        )

        assertEquals(0f, result.width(), 0.01f)
        assertEquals(0f, result.height(), 0.01f)
    }

    @Test
    fun `front camera with rotation 90`() {
        val rect = Rect(0, 0, imgW, imgH)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, imgW, imgH, viewW, viewH,
            rotationDegrees = 90, isFrontCamera = true
        )

        assertEquals(0f, result.left, 0.01f)
        assertEquals(0f, result.top, 0.01f)
        assertEquals(viewW.toFloat(), result.right, 0.01f)
        assertEquals(viewH.toFloat(), result.bottom, 0.01f)
    }

    @Test
    fun `aspect ratio mismatch maintains correct proportion`() {
        val narrowImgW = 1080
        val narrowImgH = 1920
        val rect = Rect(0, 0, 540, 960)
        val result = CoordinateTransformer.toViewCoordinates(
            rect, narrowImgW, narrowImgH, viewW, viewH,
            rotationDegrees = 0, isFrontCamera = false
        )

        assertEquals(0f, result.left, 0.01f)
        assertEquals(0f, result.top, 0.01f)
        assertEquals(viewW / 2f, result.right, 0.01f)
        assertEquals(viewH / 2f, result.bottom, 0.01f)
    }
}
