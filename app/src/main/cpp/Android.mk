LOCAL_PATH:= $(call my-dir)
include $(CLEAR_VARS)
LOCAL_MODULE := libtermux-bootstrap
LOCAL_SRC_FILES := termux-bootstrap-zip.S termux-bootstrap.c
include $(BUILD_SHARED_LIBRARY)

ifeq ($(TERMUX_PIXEL_PROBE),1)
include $(CLEAR_VARS)
LOCAL_MODULE := libtermux-pixel-probe
LOCAL_SRC_FILES := ../../pixelProbe/cpp/pixel-probe.c
include $(BUILD_SHARED_LIBRARY)
endif
