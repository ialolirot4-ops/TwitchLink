from PyQt6 import QtGui


class Palette:
    # ── Colores base del tema ──────────────────────────────────────────────
    # Acento principal: Twitch Purple (reemplaza el Windows blue #0078d7)
    PURPLE       = (145, 71, 255)
    PURPLE_DIM   = (100, 48, 180)
    PURPLE_LIGHT = (180, 138, 255)

    LIGHT = {
        QtGui.QPalette.ColorRole.Window: {
            QtGui.QPalette.ColorGroup.Disabled: (238, 236, 248),
            QtGui.QPalette.ColorGroup.Active:   (245, 243, 252),
            QtGui.QPalette.ColorGroup.Inactive: (245, 243, 252)
        },
        QtGui.QPalette.ColorRole.WindowText: {
            QtGui.QPalette.ColorGroup.Disabled: (140, 135, 160),
            QtGui.QPalette.ColorGroup.Active:   (18, 14, 32),
            QtGui.QPalette.ColorGroup.Inactive: (18, 14, 32)
        },
        QtGui.QPalette.ColorRole.Base: {
            QtGui.QPalette.ColorGroup.Disabled: (238, 236, 248),
            QtGui.QPalette.ColorGroup.Active:   (255, 255, 255),
            QtGui.QPalette.ColorGroup.Inactive: (255, 255, 255)
        },
        QtGui.QPalette.ColorRole.AlternateBase: {
            QtGui.QPalette.ColorGroup.Disabled: (240, 238, 252),
            QtGui.QPalette.ColorGroup.Active:   (240, 237, 253),
            QtGui.QPalette.ColorGroup.Inactive: (240, 237, 253)
        },
        QtGui.QPalette.ColorRole.ToolTipBase: {
            QtGui.QPalette.ColorGroup.Disabled: (250, 248, 255),
            QtGui.QPalette.ColorGroup.Active:   (250, 248, 255),
            QtGui.QPalette.ColorGroup.Inactive: (250, 248, 255)
        },
        QtGui.QPalette.ColorRole.ToolTipText: {
            QtGui.QPalette.ColorGroup.Disabled: (18, 14, 32),
            QtGui.QPalette.ColorGroup.Active:   (18, 14, 32),
            QtGui.QPalette.ColorGroup.Inactive: (18, 14, 32)
        },
        QtGui.QPalette.ColorRole.PlaceholderText: {
            QtGui.QPalette.ColorGroup.Disabled: (0, 0, 0, 90),
            QtGui.QPalette.ColorGroup.Active:   (0, 0, 0, 110),
            QtGui.QPalette.ColorGroup.Inactive: (0, 0, 0, 110)
        },
        QtGui.QPalette.ColorRole.Text: {
            QtGui.QPalette.ColorGroup.Disabled: (140, 135, 160),
            QtGui.QPalette.ColorGroup.Active:   (18, 14, 32),
            QtGui.QPalette.ColorGroup.Inactive: (18, 14, 32)
        },
        QtGui.QPalette.ColorRole.Button: {
            QtGui.QPalette.ColorGroup.Disabled: (238, 236, 248),
            QtGui.QPalette.ColorGroup.Active:   (237, 234, 250),
            QtGui.QPalette.ColorGroup.Inactive: (237, 234, 250)
        },
        QtGui.QPalette.ColorRole.ButtonText: {
            QtGui.QPalette.ColorGroup.Disabled: (140, 135, 160),
            QtGui.QPalette.ColorGroup.Active:   (18, 14, 32),
            QtGui.QPalette.ColorGroup.Inactive: (18, 14, 32)
        },
        QtGui.QPalette.ColorRole.BrightText: {
            QtGui.QPalette.ColorGroup.Disabled: (255, 255, 255),
            QtGui.QPalette.ColorGroup.Active:   (255, 255, 255),
            QtGui.QPalette.ColorGroup.Inactive: (255, 255, 255)
        },
        QtGui.QPalette.ColorRole.Light: {
            QtGui.QPalette.ColorGroup.Disabled: (255, 255, 255),
            QtGui.QPalette.ColorGroup.Active:   (255, 255, 255),
            QtGui.QPalette.ColorGroup.Inactive: (255, 255, 255)
        },
        QtGui.QPalette.ColorRole.Midlight: {
            QtGui.QPalette.ColorGroup.Disabled: (248, 246, 255),
            QtGui.QPalette.ColorGroup.Active:   (228, 225, 245),
            QtGui.QPalette.ColorGroup.Inactive: (228, 225, 245)
        },
        QtGui.QPalette.ColorRole.Dark: {
            QtGui.QPalette.ColorGroup.Disabled: (158, 154, 178),
            QtGui.QPalette.ColorGroup.Active:   (158, 154, 178),
            QtGui.QPalette.ColorGroup.Inactive: (158, 154, 178)
        },
        QtGui.QPalette.ColorRole.Mid: {
            QtGui.QPalette.ColorGroup.Disabled: (195, 192, 215),
            QtGui.QPalette.ColorGroup.Active:   (195, 192, 215),
            QtGui.QPalette.ColorGroup.Inactive: (195, 192, 215)
        },
        QtGui.QPalette.ColorRole.Shadow: {
            QtGui.QPalette.ColorGroup.Disabled: (60, 55, 85),
            QtGui.QPalette.ColorGroup.Active:   (80, 75, 108),
            QtGui.QPalette.ColorGroup.Inactive: (80, 75, 108)
        },
        QtGui.QPalette.ColorRole.Highlight: {
            QtGui.QPalette.ColorGroup.Disabled: (145, 71, 255),
            QtGui.QPalette.ColorGroup.Active:   (145, 71, 255),
            QtGui.QPalette.ColorGroup.Inactive: (230, 226, 248)
        },
        QtGui.QPalette.ColorRole.Accent: {
            QtGui.QPalette.ColorGroup.Disabled: (140, 135, 160),
            QtGui.QPalette.ColorGroup.Active:   (145, 71, 255),
            QtGui.QPalette.ColorGroup.Inactive: (230, 226, 248)
        },
        QtGui.QPalette.ColorRole.HighlightedText: {
            QtGui.QPalette.ColorGroup.Disabled: (255, 255, 255),
            QtGui.QPalette.ColorGroup.Active:   (255, 255, 255),
            QtGui.QPalette.ColorGroup.Inactive: (18, 14, 32)
        },
        QtGui.QPalette.ColorRole.Link: {
            QtGui.QPalette.ColorGroup.Disabled: (120, 58, 220),
            QtGui.QPalette.ColorGroup.Active:   (120, 58, 220),
            QtGui.QPalette.ColorGroup.Inactive: (120, 58, 220)
        },
        QtGui.QPalette.ColorRole.LinkVisited: {
            QtGui.QPalette.ColorGroup.Disabled: (80, 35, 155),
            QtGui.QPalette.ColorGroup.Active:   (80, 35, 155),
            QtGui.QPalette.ColorGroup.Inactive: (80, 35, 155)
        }
    }


    DARK = {
        QtGui.QPalette.ColorRole.Window: {
            QtGui.QPalette.ColorGroup.Disabled: (38, 36, 54),
            QtGui.QPalette.ColorGroup.Active:   (40, 38, 56),
            QtGui.QPalette.ColorGroup.Inactive: (40, 38, 56)
        },
        QtGui.QPalette.ColorRole.WindowText: {
            QtGui.QPalette.ColorGroup.Disabled: (148, 144, 172),
            QtGui.QPalette.ColorGroup.Active:   (228, 224, 245),
            QtGui.QPalette.ColorGroup.Inactive: (228, 224, 245)
        },
        QtGui.QPalette.ColorRole.Base: {
            QtGui.QPalette.ColorGroup.Disabled: (28, 26, 42),
            QtGui.QPalette.ColorGroup.Active:   (30, 28, 44),
            QtGui.QPalette.ColorGroup.Inactive: (30, 28, 44)
        },
        QtGui.QPalette.ColorRole.AlternateBase: {
            QtGui.QPalette.ColorGroup.Disabled: (46, 44, 62),
            QtGui.QPalette.ColorGroup.Active:   (48, 46, 66),
            QtGui.QPalette.ColorGroup.Inactive: (48, 46, 66)
        },
        QtGui.QPalette.ColorRole.ToolTipBase: {
            QtGui.QPalette.ColorGroup.Disabled: (52, 50, 72),
            QtGui.QPalette.ColorGroup.Active:   (52, 50, 72),
            QtGui.QPalette.ColorGroup.Inactive: (52, 50, 72)
        },
        QtGui.QPalette.ColorRole.ToolTipText: {
            QtGui.QPalette.ColorGroup.Disabled: (200, 196, 222),
            QtGui.QPalette.ColorGroup.Active:   (218, 214, 238),
            QtGui.QPalette.ColorGroup.Inactive: (218, 214, 238)
        },
        QtGui.QPalette.ColorRole.PlaceholderText: {
            QtGui.QPalette.ColorGroup.Disabled: (255, 255, 255, 80),
            QtGui.QPalette.ColorGroup.Active:   (255, 255, 255, 100),
            QtGui.QPalette.ColorGroup.Inactive: (255, 255, 255, 100)
        },
        QtGui.QPalette.ColorRole.Text: {
            QtGui.QPalette.ColorGroup.Disabled: (148, 144, 172),
            QtGui.QPalette.ColorGroup.Active:   (228, 224, 245),
            QtGui.QPalette.ColorGroup.Inactive: (228, 224, 245)
        },
        QtGui.QPalette.ColorRole.Button: {
            QtGui.QPalette.ColorGroup.Disabled: (40, 38, 56),
            QtGui.QPalette.ColorGroup.Active:   (48, 46, 66),
            QtGui.QPalette.ColorGroup.Inactive: (48, 46, 66)
        },
        QtGui.QPalette.ColorRole.ButtonText: {
            QtGui.QPalette.ColorGroup.Disabled: (148, 144, 172),
            QtGui.QPalette.ColorGroup.Active:   (228, 224, 245),
            QtGui.QPalette.ColorGroup.Inactive: (228, 224, 245)
        },
        QtGui.QPalette.ColorRole.BrightText: {
            QtGui.QPalette.ColorGroup.Disabled: (195, 168, 255),
            QtGui.QPalette.ColorGroup.Active:   (200, 172, 255),
            QtGui.QPalette.ColorGroup.Inactive: (200, 172, 255)
        },
        QtGui.QPalette.ColorRole.Light: {
            QtGui.QPalette.ColorGroup.Disabled: (88, 84, 112),
            QtGui.QPalette.ColorGroup.Active:   (95, 90, 120),
            QtGui.QPalette.ColorGroup.Inactive: (95, 90, 120)
        },
        QtGui.QPalette.ColorRole.Midlight: {
            QtGui.QPalette.ColorGroup.Disabled: (60, 58, 80),
            QtGui.QPalette.ColorGroup.Active:   (64, 62, 85),
            QtGui.QPalette.ColorGroup.Inactive: (64, 62, 85)
        },
        QtGui.QPalette.ColorRole.Dark: {
            QtGui.QPalette.ColorGroup.Disabled: (18, 16, 30),
            QtGui.QPalette.ColorGroup.Active:   (20, 18, 32),
            QtGui.QPalette.ColorGroup.Inactive: (20, 18, 32)
        },
        QtGui.QPalette.ColorRole.Mid: {
            QtGui.QPalette.ColorGroup.Disabled: (34, 32, 50),
            QtGui.QPalette.ColorGroup.Active:   (36, 34, 52),
            QtGui.QPalette.ColorGroup.Inactive: (36, 34, 52)
        },
        QtGui.QPalette.ColorRole.Shadow: {
            QtGui.QPalette.ColorGroup.Disabled: (0, 0, 0),
            QtGui.QPalette.ColorGroup.Active:   (0, 0, 0),
            QtGui.QPalette.ColorGroup.Inactive: (0, 0, 0)
        },
        QtGui.QPalette.ColorRole.Highlight: {
            QtGui.QPalette.ColorGroup.Disabled: (100, 48, 180),
            QtGui.QPalette.ColorGroup.Active:   (145, 71, 255),
            QtGui.QPalette.ColorGroup.Inactive: (28, 26, 42)
        },
        QtGui.QPalette.ColorRole.Accent: {
            QtGui.QPalette.ColorGroup.Disabled: (148, 144, 172),
            QtGui.QPalette.ColorGroup.Active:   (145, 71, 255),
            QtGui.QPalette.ColorGroup.Inactive: (28, 26, 42)
        },
        QtGui.QPalette.ColorRole.HighlightedText: {
            QtGui.QPalette.ColorGroup.Disabled: (228, 224, 245),
            QtGui.QPalette.ColorGroup.Active:   (255, 255, 255),
            QtGui.QPalette.ColorGroup.Inactive: (228, 224, 245)
        },
        QtGui.QPalette.ColorRole.Link: {
            QtGui.QPalette.ColorGroup.Disabled: (148, 112, 240),
            QtGui.QPalette.ColorGroup.Active:   (175, 135, 255),
            QtGui.QPalette.ColorGroup.Inactive: (175, 135, 255)
        },
        QtGui.QPalette.ColorRole.LinkVisited: {
            QtGui.QPalette.ColorGroup.Disabled: (100, 55, 200),
            QtGui.QPalette.ColorGroup.Active:   (120, 68, 220),
            QtGui.QPalette.ColorGroup.Inactive: (120, 68, 220)
        }
    }
