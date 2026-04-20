"""
blur.py — Applies Windows 10/11 frosted glass / acrylic blur effects.
"""

import ctypes
from ctypes import c_int, c_uint, Structure, sizeof, byref, POINTER

class ACCENTPOLICY(Structure):
    _fields_ = [
        ("AccentState", c_uint),
        ("AccentFlags", c_uint),
        ("GradientColor", c_uint),
        ("AnimationId", c_uint)
    ]

class WINDOWCOMPOSITIONATTRIBDATA(Structure):
    _fields_ = [
        ("Attribute", c_int),
        ("Data", POINTER(ACCENTPOLICY)),
        ("SizeOfData", c_uint)
    ]

def apply_acrylic_blur(hwnd: int) -> None:
    """
    Applies a real OS-level frosted glass effect to a translucent window.
    """
    try:
        user32 = ctypes.windll.user32
        
        # 4 = ACCENT_ENABLE_ACRYLICBLURBEHIND (Windows 10 1803+ acrylic)
        policy = ACCENTPOLICY()
        policy.AccentState = 4
        # 2 = Window coordinate space for gradients
        policy.AccentFlags = 2  
        # Provide a subtle dark gradient color hint: AABBGGRR
        # We'll use 0xB0111111 = ~70% opaque very dark grey
        policy.GradientColor = 0xB0111111 
        
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.SizeOfData = sizeof(policy)
        data.Data = ctypes.pointer(policy)
        
        user32.SetWindowCompositionAttribute(hwnd, byref(data))
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Could not apply window blur: %s", exc)
