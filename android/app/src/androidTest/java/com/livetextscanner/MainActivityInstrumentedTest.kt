package com.livetextscanner

import android.Manifest
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.*
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.rule.GrantPermissionRule
import org.hamcrest.Matchers.allOf
import org.hamcrest.Matchers.not
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class MainActivityInstrumentedTest {

    @get:Rule
    val activityRule = ActivityScenarioRule(MainActivity::class.java)

    @get:Rule
    val cameraPermissionRule: GrantPermissionRule =
        GrantPermissionRule.grant(Manifest.permission.CAMERA)

    @Test
    fun activity_launchesSuccessfully() {
        onView(withId(R.id.container)).check(matches(isDisplayed()))
    }

    @Test
    fun previewView_isDisplayed() {
        onView(withId(R.id.previewView)).check(matches(isDisplayed()))
    }

    @Test
    fun textOverlay_isDisplayed() {
        onView(withId(R.id.textOverlay)).check(matches(isDisplayed()))
    }

    @Test
    fun switchCameraButton_isDisplayed() {
        onView(withId(R.id.btnSwitchCamera)).check(matches(isDisplayed()))
    }

    @Test
    fun switchCameraButton_isClickable() {
        onView(withId(R.id.btnSwitchCamera)).check(matches(isClickable()))
    }

    @Test
    fun copyButton_isDisplayed() {
        onView(withId(R.id.btnCopyText)).check(matches(isDisplayed()))
    }

    @Test
    fun copyButton_displaysCorrectText() {
        onView(withId(R.id.btnCopyText)).check(matches(withText(R.string.copy_text)))
    }

    @Test
    fun copyButton_isClickable() {
        onView(withId(R.id.btnCopyText)).check(matches(isClickable()))
    }

    @Test
    fun noTextIndicator_isInitiallyGone() {
        onView(withId(R.id.tvNoText)).check(matches(not(isDisplayed())))
    }

    @Test
    fun initializingIndicator_isDisplayedInitially() {
        onView(withId(R.id.progressInitializing)).check(matches(isDisplayed()))
    }

    @Test
    fun copyButton_hasCorrectIcon() {
        onView(
            allOf(
                withId(R.id.btnCopyText),
                withText(R.string.copy_text)
            )
        ).check(matches(isDisplayed()))
    }

    @Test
    fun switchCameraButton_hasContentDescription() {
        onView(withId(R.id.btnSwitchCamera))
            .check(matches(withContentDescription(R.string.switch_camera)))
    }

    @Test
    fun clickCopyButton_whenNoText_showsNoTextSnackbar() {
        onView(withId(R.id.btnCopyText)).perform(click())
    }

    @Test
    fun clickSwitchCamera_togglesCamera() {
        onView(withId(R.id.btnSwitchCamera)).perform(click())
        onView(withId(R.id.btnSwitchCamera)).perform(click())
    }

    @Test
    fun multipleCameraSwitches_doesNotCrash() {
        repeat(5) {
            onView(withId(R.id.btnSwitchCamera)).perform(click())
        }
    }
}
