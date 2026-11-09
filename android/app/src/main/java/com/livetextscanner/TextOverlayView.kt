package com.livetextscanner

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View

class TextOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private val blocks = mutableListOf<DetectedBlock>()

    private val highlightPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(77, 100, 200, 255)
        style = Paint.Style.FILL
    }

    private val borderPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(180, 0, 150, 255)
        style = Paint.Style.STROKE
        strokeWidth = 2f
    }

    private val flashPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(0, 255, 255, 255)
        style = Paint.Style.FILL
    }

    private val noTextPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(180, 255, 255, 255)
        textSize = 48f
        textAlign = Paint.Align.CENTER
    }

    private var flashAlpha = 0
    private var flashAnimator: ValueAnimator? = null
    private var showNoText = false

    fun setTextBlocks(textBlocks: List<DetectedBlock>) {
        blocks.clear()
        blocks.addAll(textBlocks)
        showNoText = textBlocks.isEmpty()
        invalidate()
    }

    fun triggerFlash() {
        flashAnimator?.cancel()
        flashAlpha = 120
        flashAnimator = ValueAnimator.ofInt(120, 0).apply {
            duration = 400
            addUpdateListener { animator ->
                flashAlpha = animator.animatedValue as Int
                flashPaint.color = Color.argb(flashAlpha, 255, 255, 255)
                invalidate()
            }
            start()
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)

        if (blocks.isEmpty()) {
            if (showNoText) {
                val cx = width / 2f
                val cy = height / 2f
                canvas.drawText(
                    context.getString(R.string.no_text_detected),
                    cx,
                    cy,
                    noTextPaint
                )
            }
            return
        }

        for (block in blocks) {
            val rect = block.boundingBox
            canvas.drawRect(rect, highlightPaint)
            canvas.drawRect(rect, borderPaint)
        }

        if (flashAlpha > 0) {
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), flashPaint)
        }
    }
}
