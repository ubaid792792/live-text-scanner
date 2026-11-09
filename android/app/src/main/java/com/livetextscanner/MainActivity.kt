package com.livetextscanner

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Size
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.AspectRatio
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.livetextscanner.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var viewModel: CameraViewModel
    private var camera: Camera? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var lensFacing = CameraSelector.LENS_FACING_BACK

    private val textRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    private var isProcessing = false

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            viewModel.setModelReady(true)
            startCamera()
        } else {
            showPermissionDeniedDialog()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        viewModel = ViewModelProvider(this)[CameraViewModel::class.java]

        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY

        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        window.statusBarColor = android.graphics.Color.TRANSPARENT

        binding.btnSwitchCamera.setOnClickListener { switchCamera() }
        binding.btnCopyText.setOnClickListener { copyText() }

        observeViewModel()
        checkCameraPermission()
    }

    private fun observeViewModel() {
        viewModel.detectedBlocks.observe(this) { blocks ->
            binding.textOverlay.setTextBlocks(blocks)
        }

        viewModel.textDetected.observe(this) { hasText ->
            binding.tvNoText.visibility = if (!hasText && viewModel.isModelReady.value) {
                View.VISIBLE
            } else {
                View.GONE
            }
        }

        viewModel.isModelReady.observe(this) { ready ->
            if (ready) {
                binding.progressInitializing.visibility = View.GONE
                binding.tvInitializing.visibility = View.GONE
            } else {
                binding.progressInitializing.visibility = View.VISIBLE
                binding.tvInitializing.visibility = View.VISIBLE
            }
        }
    }

    private fun checkCameraPermission() {
        if (!packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA)) {
            AlertDialog.Builder(this)
                .setTitle("No Camera")
                .setMessage(R.string.no_camera)
                .setPositiveButton(android.R.string.ok) { finish() }
                .show()
            return
        }

        when {
            ContextCompat.checkSelfPermission(
                this, Manifest.permission.CAMERA
            ) == PackageManager.PERMISSION_GRANTED -> {
                viewModel.setModelReady(true)
                startCamera()
            }
            shouldShowRequestPermissionRationale(Manifest.permission.CAMERA) -> {
                showPermissionRationale()
            }
            else -> {
                permissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }

    private fun showPermissionRationale() {
        AlertDialog.Builder(this)
            .setTitle("Camera Permission")
            .setMessage(R.string.camera_permission_rationale)
            .setPositiveButton(R.string.ok) { _, _ ->
                permissionLauncher.launch(Manifest.permission.CAMERA)
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun showPermissionDeniedDialog() {
        AlertDialog.Builder(this)
            .setTitle("Permission Denied")
            .setMessage(R.string.camera_permission_denied)
            .setPositiveButton(R.string.settings) { _, _ ->
                startActivity(
                    android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS.let {
                        android.content.Intent(it).apply {
                            data = android.net.Uri.fromParts("package", packageName, null)
                        }
                    }
                )
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            cameraProvider = cameraProviderFuture.get()
            bindCamera()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun bindCamera() {
        val provider = cameraProvider ?: return
        provider.unbindAll()

        val preview = Preview.Builder()
            .setTargetAspectRatio(AspectRatio.RATIO_16_9)
            .build()
            .also { it.setSurfaceProvider(binding.previewView.surfaceProvider) }

        val imageAnalysis = ImageAnalysis.Builder()
            .setTargetResolution(Size(1080, 1920))
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
            .also { analysis ->
                analysis.setAnalyzer(ContextCompat.getMainExecutor(this)) { imageProxy ->
                    processImage(imageProxy)
                }
            }

        val cameraSelector = CameraSelector.Builder()
            .requireLensFacing(lensFacing)
            .build()

        try {
            camera = provider.bindToLifecycle(
                this as LifecycleOwner,
                cameraSelector,
                preview,
                imageAnalysis
            )
            viewModel.lensFacing = lensFacing
        } catch (e: Exception) {
            viewModel.setModelReady(true)
            binding.progressInitializing.visibility = View.GONE
            binding.tvInitializing.visibility = View.GONE
            AlertDialog.Builder(this)
                .setTitle("Camera Error")
                .setMessage("Failed to initialize camera: ${e.message}")
                .setPositiveButton(android.R.string.ok, null)
                .show()
        }
    }

    private fun processImage(imageProxy: ImageProxy) {
        if (isProcessing) {
            imageProxy.close()
            return
        }

        val mediaImage = imageProxy.image ?: run {
            imageProxy.close()
            return
        }

        isProcessing = true

        lifecycleScope.launch(Dispatchers.Default) {
            val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)

            try {
                val visionText = textRecognizer.process(image).await()

                val blocks = mutableListOf<DetectedBlock>()
                val textBuilder = StringBuilder()
                val imageWidth = imageProxy.width
                val imageHeight = imageProxy.height
                val viewWidth = binding.textOverlay.width
                val viewHeight = binding.textOverlay.height
                val rotationDegrees = imageProxy.imageInfo.rotationDegrees
                val isFrontCamera = lensFacing == CameraSelector.LENS_FACING_FRONT

                for (block in visionText.textBlocks) {
                    val blockRect = block.boundingBox ?: continue
                    if (blockRect.isEmpty) continue

                    val transformed = CoordinateTransformer.toViewCoordinates(
                        blockRect, imageWidth, imageHeight,
                        viewWidth, viewHeight, rotationDegrees, isFrontCamera
                    )

                    val blockText = block.text.trim()
                    if (blockText.isNotEmpty()) {
                        blocks.add(DetectedBlock(blockText, transformed))

                        if (textBuilder.isNotEmpty()) textBuilder.append('\n')
                        textBuilder.append(blockText)
                    }
                }

                withContext(Dispatchers.Main) {
                    viewModel.updateDetectedText(blocks, textBuilder.toString())
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    viewModel.clearDetectedText()
                }
            } finally {
                imageProxy.close()
                isProcessing = false
            }
        }
    }

    private suspend fun <T> com.google.mlkit.common.Task<T>.await(): T {
        return kotlinx.coroutines.suspendCancellableCoroutine { continuation ->
            addOnSuccessListener { result ->
                if (continuation.isActive) continuation.resume(result) {}
            }
            addOnFailureListener { exception ->
                if (continuation.isActive) continuation.resumeWithException(exception)
            }
            addOnCanceledListener {
                if (continuation.isActive)
                    continuation.cancel()
            }
        }
    }

    private fun switchCamera() {
        lensFacing = if (lensFacing == CameraSelector.LENS_FACING_BACK) {
            CameraSelector.LENS_FACING_FRONT
        } else {
            CameraSelector.LENS_FACING_BACK
        }
        bindCamera()
    }

    private fun copyText() {
        val text = viewModel.concatenatedText.value
        if (text.isEmpty()) {
            Snackbar.make(binding.root, R.string.no_text_detected, Snackbar.LENGTH_SHORT).show()
            return
        }

        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText("scanned_text", text)
        clipboard.setPrimaryClip(clip)

        Snackbar.make(binding.root, R.string.text_copied, Snackbar.LENGTH_SHORT)
            .setAction(R.string.ok) { }
            .show()

        viewModel.triggerFlash()
        binding.textOverlay.triggerFlash()

        binding.textOverlay.postDelayed({
            viewModel.clearFlash()
        }, 500)
    }

    override fun onResume() {
        super.onResume()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            == PackageManager.PERMISSION_GRANTED
        ) {
            if (cameraProvider == null) {
                startCamera()
            } else {
                bindCamera()
            }
        }
    }

    override fun onPause() {
        super.onPause()
        cameraProvider?.unbindAll()
    }

    override fun onDestroy() {
        super.onDestroy()
        textRecognizer.close()
    }
}
