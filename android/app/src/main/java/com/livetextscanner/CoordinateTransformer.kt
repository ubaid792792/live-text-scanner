package com.livetextscanner

import android.graphics.Rect
import android.graphics.RectF

object CoordinateTransformer {

    fun toViewCoordinates(
        rect: Rect,
        imageWidth: Int,
        imageHeight: Int,
        viewWidth: Int,
        viewHeight: Int,
        rotationDegrees: Int,
        isFrontCamera: Boolean
    ): RectF {
        val corners = arrayOf(
            floatArrayOf(rect.left.toFloat(), rect.top.toFloat()),
            floatArrayOf(rect.right.toFloat(), rect.top.toFloat()),
            floatArrayOf(rect.right.toFloat(), rect.bottom.toFloat()),
            floatArrayOf(rect.left.toFloat(), rect.bottom.toFloat())
        )

        for (corner in corners) {
            corner[0] /= imageWidth
            corner[1] /= imageHeight
        }

        for (corner in corners) {
            val x = corner[0]
            val y = corner[1]
            when (rotationDegrees) {
                90 -> { corner[0] = y; corner[1] = 1 - x }
                180 -> { corner[0] = 1 - x; corner[1] = 1 - y }
                270 -> { corner[0] = 1 - y; corner[1] = x }
            }
        }

        if (isFrontCamera) {
            for (corner in corners) {
                corner[0] = 1 - corner[0]
            }
        }

        var minX = Float.MAX_VALUE
        var minY = Float.MAX_VALUE
        var maxX = Float.MIN_VALUE
        var maxY = Float.MIN_VALUE

        for (corner in corners) {
            corner[0] *= viewWidth
            corner[1] *= viewHeight
            if (corner[0] < minX) minX = corner[0]
            if (corner[1] < minY) minY = corner[1]
            if (corner[0] > maxX) maxX = corner[0]
            if (corner[1] > maxY) maxY = corner[1]
        }

        return RectF(minX, minY, maxX, maxY)
    }
}
