"resource/UI/InGameMainMenu.res"
// Urik: 16x10 16x9 & non-wide ready
// This mod should support tripple-monitor 48:9 & 48:10 modes, but not fully tested.
{
	"InGameMainMenu"
	{
		"ControlName"			"Frame"
		"fieldName"				"InGameMainMenu"
		"xpos"					"0"
		"ypos"					"0"
		"wide"					"f0"
		"tall"					"f0"
		"autoResize"			"0"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"PaintBackgroundType"	"0"
	}
		
	"PnlBackground_tweaks1"  //上方准星之类的黑块
	{
		"ControlName"		"EditablePanel"
		"fieldName"			"PnlBackground_tweaks1"
		"xpos"				"0"	[$WIN32WIDE]
		"xpos"				"0"	[!$WIN32WIDE]
		"ypos"				"0"
		"zpos"				"-1"
		"wide"				"f0"	[$WIN32WIDE]
		"wide"				"f0"	[!$WIN32WIDE]
		"tall"				"f0"
		"visible"			"1"			
		"enabled"			"1"
		"bgcolor_override"	"0 0 0 200"
		"PaintBackgroundType"	"0"
		"PnlBackground_tweaks2"
		{
			"ControlName"		"EditablePanel"
			"fieldName"			"PnlBackground_tweaks2"
			"xpos"				"-10"
			"ypos"				"0"
			"zpos"				"0"
			"wide"				"602"	[$WIN32WIDE]
			"wide"				"420"	[!$WIN32WIDE]
			"tall"				"28"
			"visible"			"1"			
			"enabled"			"1"
			"bgcolor_override"	"0 0 0 0"
			"PaintBackgroundType"	"3"
		}
	}	
	
	"PnlBackground_Sliders" //右侧的黑块
	{
		"ControlName"		"EditablePanel"
		"fieldName"			"PnlBackground_Sliders"
		"xpos"				"c266"	[$WIN32WIDE]
		"xpos"				"r118"	[!$WIN32WIDE]
		"ypos"				"94"
		"zpos"				"1"
		"wide"				"f0"
		"tall"				"280"
		"visible"			"0"			
		"enabled"			"0"
		"bgcolor_override"	"0 0 0 167"
		"PaintBackgroundType"	"0"
	}
	
	"PnlBackground_Sliders2" //下侧的黑块
	{
		"ControlName"		"EditablePanel"
		"fieldName"			"PnlBackground_Sliders2"
		"xpos"				"0"	[$WIN32WIDE]  //c266
		"xpos"				"0"	[!$WIN32WIDE]
		"ypos"				"410" //94
		"zpos"				"1"
		"wide"				"f0"
		"tall"				"f0"
		"visible"			"0"			
		"enabled"			"0"
		"bgcolor_override"	"0 0 0 167"
		"PaintBackgroundType"	"0"
	}
	
	"DrpCrosshair"
	{
		"ControlName"		"DropDownMenu"
		"fieldName"			"DrpCrosshair"
		"xpos"				"12"	[$WIN32WIDE]
		"xpos"				"12"	[!$WIN32WIDE]
		"ypos"				"43"//buttons_ypos
		"zpos"				"3"
		"wide"				"184"
		"tall"				"20"
		"visible"			"1"
		"enabled"			"1"
		"usetitlesafe"		"0"
		"tabPosition"		"0"
		//"bgcolor_override"		"0 0 0 128"//q_buttons_bgcolor
		"navLeft"				"DrpPrecisionAssist"
		"navRight"				"DrpNetGraph"
		"navUp"				"BtnExitToMainMenu"
		"navDown"			"DrpNetGraph"
		//button and label
		"BtnDropButton"
		{
			"ControlName"				"L4D360HybridButton"
			"fieldName"					"BtnDropButton"
			"xpos"						"0"
			"ypos"						"0"
			"zpos"						"3"
			"wide"						"184"
			"wideatopen"				"0"//wideatopen
			"tall"						"15"
			"autoResize"				"1"
			"pinCorner"					"0"
			"visible"					"1"
			"enabled"					"1"
			"tabPosition"				"1"
			"AllCaps"					"1"
			"textalignment"				"center"
			"labelText"					"准星设置" [!$RUSSIAN]
			"tooltiptext"				""
			"style"					"SmallButton"
			"command"					"FlmCrosshair"
			"ActivationType"			"0"
			"OnlyActiveUser"			"1"
		}
	}
	"DrpNetGraph"
	{
		"ControlName"		"DropDownMenu"
		"fieldName"			"DrpNetGraph"
		"xpos"				"12"	[$WIN32WIDE]
		"xpos"				"12"	[!$WIN32WIDE]
		"ypos"				"68"//buttons_ypos
		"zpos"				"3"
		"wide"				"184"
		"tall"				"20"
		"visible"			"1"
		"enabled"			"1"
		"usetitlesafe"		"0"
		"tabPosition"		"0"
		//"bgcolor_override"		"0 0 0 128"//q_buttons_bgcolor
		"navLeft"				"DrpCrosshair"
		"navRight"				"DrpSplitScreenMode"
		"navUp"				"DrpCrosshair"
		"navDown"			"DrpSplitScreenMode"
		//button and label
		"BtnDropButton"
		{
			"ControlName"				"L4D360HybridButton"
			"fieldName"					"BtnDropButton"
			"xpos"						"0"
			"ypos"						"0"
			"zpos"						"3"
			"wide"						"184"
			"wideatopen"				"0"//wideatopen
			"tall"						"15"
			"autoResize"				"1"
			"pinCorner"					"0"
			"visible"					"1"
			"enabled"					"1"
			"tabPosition"				"1"
			"AllCaps"					"1"
			"textalignment"				"center"
			"labelText"					"网络图"
			"tooltiptext"				""
		"style"					"SmallButton"
			"command"					"FlmNetGraph"
			"ActivationType"			"0"
			"OnlyActiveUser"			"1"
		}
	}		
	"DrpSplitScreenMode"
	{
		"ControlName"		"DropDownMenu"
		"fieldName"			"DrpSplitScreenMode"
		"xpos"				"12"	[$WIN32WIDE]
		"xpos"				"12"	[!$WIN32WIDE]
		"ypos"				"93"//buttons_ypos
		"zpos"				"3"
		"wide"				"184"
		"tall"				"20"
		// doesn't work unfortunately
		// "if_split_screen_vertical"
		// {
		// "visible"			"1"
		// "enabled"			"1"
		// }
		// "if_split_screen_horizontal"
		// {
		// "visible"			"1"
		// "enabled"			"1"
		// }
		"visible"			"1"
		"enabled"			"1"
		"usetitlesafe"		"0"
		"tabPosition"		"0"
		//"bgcolor_override"		"0 0 0 128"//q_buttons_bgcolor
		"navLeft"				"DrpNetGraph"
		"navRight"				"QuickKickPlayer"
		"navUp"				"DrpNetGraph"
		"navDown"			"QuickKickPlayer"
		//button and label
		"BtnDropButton"
		{
			"ControlName"				"L4D360HybridButton"
			"fieldName"					"BtnDropButton"
			"xpos"						"0"
			"ypos"						"0"
			"zpos"						"3"
			"wide"						"184"
			"wideatopen"				"0"//wideatopen
			"tall"						"15"
			"autoResize"				"1"
			"pinCorner"					"0"
			"visible"					"1"
			"enabled"					"1"
			"tabPosition"				"1"
			"AllCaps"					"1"
			"textalignment"				"center"
			"labelText"					"分屏模式"
			"tooltiptext"				""
			"style"					"SmallButton"
			"command"					"FlmSplitScreenMode"
			"ActivationType"			"0"
			"OnlyActiveUser"			"1"
		}
	}
	// "ImgKick"
	// {
		// "ControlName"			"ImagePanel"
		// "fieldName"				"ImgKick"
		// "xpos"					"c-24"	[$WIN32WIDE]
		// "xpos"					"380"	[!$WIN32WIDE]
		// "ypos"					"102"
		// "wide"					"10"
		// "tall"					"10"
		// "visible"				"1"
		// "enabled"				"1"
		// "image"					"ingamemenu/icon_button_kick"
		// "scaleimage"				"1"
		// "zpos"					"2"
	// }
	"QuickKickPlayer"
	{
		"ControlName"				"L4D360HybridButton"
		"fieldName"					"QuickKickPlayer"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"						"118"
		"zpos"						"3"
		"wide"						"184"
		"tall"						"20"
		//"autoResize"				"1"
		//"pinCorner"					"0"
		"visible"					"1"
		"enabled"					"1"
		//"tabPosition"				"1"
		"AllCaps"					"1"
		"textalignment"				"west"
		"labelText"					"#L4D360UI_BootPlayer"
		"tooltiptext"				"#L4D360UI_BootPlayer_Tip"
		"style"					"SmallButton"
		"command"					"BootPlayer"
		"ActivationType"			"0"
		"OnlyActiveUser"			"1"
		"navLeft"				"DrpSplitScreenMode"
		"navRight"				"DrpPrecisionAssist"
		"navUp"				"DrpSplitScreenMode"
		"navDown"			"DrpTvGammaHint"
		//"Font"					"BlogPostText"
		//"centerwrap"				"0"
		//"textalignment"			"center"
		//"defaultBgColor_override"		"0 0 0 100"
		//"armedBgColor_override"		"0 0 0 0"
 		//"depressedBgColor_override"	"0 0 0 50"
		// "paintborder"				"0"
		// "sound_armed"				""
		// "sound_depressed"			""
		// "sound_released"			""
	}

	"Time_sec01"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Time_sec01"
		"xpos"					"140"	[$WIN32WIDE]
		"xpos"					"140"	[!$WIN32WIDE]
		"ypos"					"12"
		"wide"					"12"
		"tall"					"24"
		"visible"				"1"
		"enabled"				"1"
		"image"					"ingamemenu/sec01"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	"Time_sec10"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Time_sec10"
		"xpos"					"128"	[$WIN32WIDE]
		"xpos"					"128"	[!$WIN32WIDE]
		"ypos"					"12"
		"wide"					"12"
		"tall"					"24"
		"visible"				"1"
		"enabled"				"1"
		"image"					"ingamemenu/sec10"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	"ms"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ms"
		"xpos"					"116"	[$WIN32WIDE]
		"xpos"					"116"	[!$WIN32WIDE]
		"ypos"					"12"
		"wide"					"12"
		"tall"					"24"
		"visible"				"1"
		"enabled"				"1"
		"image"					"ingamemenu/hmm"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	"Time_min01"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Time_min01"
		"xpos"					"104"	[$WIN32WIDE]
		"xpos"					"104"	[!$WIN32WIDE]
		"ypos"					"12"
		"wide"					"12"
		"tall"					"24"
		"visible"				"1"
		"enabled"				"1"
		"image"					"ingamemenu/min01"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	"Time_min10"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Time_min10"
		"xpos"					"92"	[$WIN32WIDE]
		"xpos"					"92"	[!$WIN32WIDE]
		"ypos"					"12"
		"wide"					"12"
		"tall"					"24"
		"visible"				"1"
		"enabled"				"1"
		"image"					"ingamemenu/min10"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	"hm"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"hm"
		"xpos"					"80"	[$WIN32WIDE]
		"xpos"					"80"	[!$WIN32WIDE]
		"ypos"					"12"
		"wide"					"12"
		"tall"					"24"
		"visible"				"1"
		"enabled"				"1"
		"image"					"ingamemenu/hmm"
		"scaleimage"				"1"
		"zpos"					"2"
		//drawcolor_special_event_autoreplace
	}
	"Time_hour01"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Time_hour01"
		"xpos"					"68"	[$WIN32WIDE]
		"xpos"					"68"	[!$WIN32WIDE]
		"ypos"					"12"
		"wide"					"12"
		"tall"					"24"
		"visible"				"1"
		"enabled"				"1"
		"image"					"ingamemenu/hour01"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	"Time_hour10"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Time_hour10"
		"xpos"					"56"	[$WIN32WIDE]
		"xpos"					"56"	[!$WIN32WIDE]
		"ypos"					"12"
		"wide"					"12"
		"tall"					"24"
		"visible"				"1"
		"enabled"				"1"
		"image"					"ingamemenu/hour10"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	"ImgSpeaker"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgSpeaker"
		"xpos"					"c282"	[$WIN32WIDE]
		"xpos"					"r102"	[!$WIN32WIDE]
		"ypos"					"143"
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"ingamemenu/icon_sound"
		"scaleimage"				"1"
		"zpos"					"2"
		//drawcolor_special_event_autoreplace
	}
	// 音量大小
	"SldGameVolume"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldGameVolume"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"14"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0.0"
		"maxValue"				"1.0"
		"stepSize"				"0.1"
		"conCommand"			"volume"
		"inverseFill"			"0"
		"navUp"				"cam_collision"
		"navDown"			"SldMusicVolume"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"游戏音量"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	// 音乐大小
	"ImgMusic"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgMusic"
		"xpos"					"c282"	[$WIN32WIDE]
		"xpos"					"r102"	[!$WIN32WIDE]
		"ypos"					"163"
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"ingamemenu/icon_music"
		"scaleimage"				"1"
		"zpos"					"2"
		//drawcolor_special_event_autoreplace
	}	
	"SldMusicVolume"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldMusicVolume"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"33"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0.0"
		"maxValue"				"1.0"
		"stepSize"				"0.1"
		"conCommand"			"snd_musicvolume"
		"inverseFill"			"0"
		"navUp"				"SldGameVolume"
		"navDown"			"SldGamma"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"音乐音量"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"ImgGamma"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgGamma"
		"xpos"					"c282"	[$WIN32WIDE]
		"xpos"					"r102"	[!$WIN32WIDE]
		"ypos"					"183"
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"ingamemenu/icon_brightness"
		"scaleimage"				"1"
		"zpos"					"2"
		//drawcolor_special_event_autoreplace
	}
	// 亮度
	"SldGamma"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldGamma"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"52"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"1.6"
		"maxValue"				"2.6"
		"stepSize"				"0.1"
		"conCommand"			"mat_monitorgamma"
		"inverseFill"			"0"
		"navUp"				"SldMusicVolume"
		"navDown"			"SldGamma1"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"屏幕伽马"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"ImgBrightness"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgBrightness"
		"xpos"					"c282"	[$WIN32WIDE]
		"xpos"					"r102"	[!$WIN32WIDE]
		"ypos"					"203"
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"ingamemenu/icon_brightness"
		"scaleimage"				"1"
		"zpos"					"2"
		"drawcolor"		"96 96 96 255"//disable_for_special_event
		//drawcolor_special_event_autoreplace
	}	
	"Plus"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Plus"
		"xpos"					"c292"	[$WIN32WIDE]
		"xpos"					"r92"	[!$WIN32WIDE]
		"ypos"					"205"
		"wide"					"6"
		"tall"					"6"
		"visible"				"0"
		"enabled"				"1"
		"image"					"ingamemenu/plus"
		"scaleimage"				"1"
		"zpos"					"2"
		"drawcolor"		"96 96 96 255"//disable_for_special_event
		//drawcolor_special_event_autoreplace
	}
	"DrpTvGammaHint"
	{
		"navup" "QuickKickPlayer"
		"navdown" "DrpCaptionsHint"
		"ControlName"		"DropDownMenu"
		"fieldName"			"DrpTvGammaHint"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"143"
		"wide"					"184"
		"tall"					"20"
		"zpos"				"3"
		"visible"			"1"
		"enabled"			"1"
		"usetitlesafe"		"0"
		"tabPosition"		"0"
		//"bgcolor_override"		"255 0 255 128"//q_buttons_bgcolor
		//button and label
		"BtnDropButton"
		{
			"ControlName"				"L4D360HybridButton"
			"fieldName"					"BtnDropButton"
			"xpos"						"0"
			"ypos"						"0"
			"zpos"						"3"
			"wide"						"184"
			"wideatopen"				"0"//wideatopen
			"tall"						"20"
			"autoResize"				"1"
			"pinCorner"					"0"
			"visible"					"1"
			"enabled"					"1"
			"tabPosition"				"1"
			"AllCaps"					"1"
			"textalignment"				"center"
			"labelText"					"电视亮度说明"
			"tooltiptext"				""
		"style"					"SmallButton"
			"command"					"FlmTvGammaHint"
			"ActivationType"			"0"
			"OnlyActiveUser"			"1"
		}
	}
	// 显示器亮度				
	"SldGamma1"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldGamma1"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"71"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"conCommand"			"mat_monitorgamma_tv_enabled"
		"inverseFill"			"0"
		"navUp"				"SldGamma"
		"navDown"			"SldCaptions"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"电视亮度模式"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"ImgCaptions"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgCaptions"
		"xpos"					"c282"	[$WIN32WIDE]
		"xpos"					"r102"	[!$WIN32WIDE]
		"ypos"					"243"
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"ingamemenu/icon_ccaptions"
		"scaleimage"				"1"
		"zpos"					"2"
		//drawcolor_special_event_autoreplace
	}
	"DrpCaptionsHint"
	{
		"navup" "DrpTvGammaHint"
		"navdown" "DrpGameInstructorHint"
		"ControlName"		"DropDownMenu"
		"fieldName"			"DrpCaptionsHint"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"168"
		"wide"					"184"
		"tall"					"20"
		"zpos"				"3"
		"visible"			"1"
		"enabled"			"1"
		"usetitlesafe"		"0"
		"tabPosition"		"0"
		//"bgcolor_override"		"255 0 255 128"//q_buttons_bgcolor
		//button and label
		"BtnDropButton"
		{
			"ControlName"				"L4D360HybridButton"
			"fieldName"					"BtnDropButton"
			"xpos"						"0"
			"ypos"						"0"
			"zpos"						"3"
			"wide"						"184"
			"wideatopen"				"0"//wideatopen
			"tall"						"20"
			"autoResize"				"1"
			"pinCorner"					"0"
			"visible"					"1"
			"enabled"					"1"
			"tabPosition"				"1"
			"AllCaps"					"1"
			"textalignment"				"center"
			"labelText"					"字幕说明"
			"tooltiptext"				""
		"style"					"SmallButton"
			"command"					"FlmCaptionsHint"
			"ActivationType"			"0"
			"OnlyActiveUser"			"1"
		}
	}
	// 字幕 6
	"SldCaptions"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldCaptions"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"90"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"conCommand"			"closecaption"
		"inverseFill"			"0"
		"navUp"				"SldGamma1"
		"navDown"			"SldGameInstructor"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"字幕"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"ImgGameInstructor"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgGameInstructor"
		"xpos"					"c282"	[$WIN32WIDE]
		"xpos"					"r102"	[!$WIN32WIDE]
		"ypos"					"222"
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"ingamemenu/icon_info"
		"scaleimage"				"1"
		"zpos"					"2"
		//drawcolor_special_event_autoreplace
	}
	"DrpGameInstructorHint"
	{
		"navup" "DrpCaptionsHint"
		"navdown" "BtnReturnToGame"
		"ControlName"		"DropDownMenu"
		"fieldName"			"DrpGameInstructorHint"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"193"
		"wide"					"184"
		"tall"					"20"
		"zpos"				"3"
		"visible"			"1"
		"enabled"			"1"
		"usetitlesafe"		"0"
		"tabPosition"		"0"
		//"bgcolor_override"		"255 0 255 128"//q_buttons_bgcolor
		//button and label
		"BtnDropButton"
		{
			"ControlName"				"L4D360HybridButton"
			"fieldName"					"BtnDropButton"
			"xpos"						"0"
			"ypos"						"0"
			"zpos"						"3"
			"wide"						"184"
			"wideatopen"				"0"//wideatopen
			"tall"						"20"
			"autoResize"				"1"
			"pinCorner"					"0"
			"visible"					"1"
			"enabled"					"1"
			"tabPosition"				"1"
			"AllCaps"					"1"
			"textalignment"				"center"
			"labelText"					"游戏提示说明"
			"tooltiptext"				""
		"style"					"SmallButton"
			"command"					"FlmGameInstructorHint"
			"ActivationType"			"0"
			"OnlyActiveUser"			"1"
		}
	}
	// 5
	"SldGameInstructor"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldGameInstructor"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"109"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"conCommand"			"gameinstructor_enable"
		"inverseFill"			"0"
		"navUp"				"SldCaptions"
		"navDown"			"SldFOVBC" // 6
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"游戏提示"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"ImgFOV"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgFOV"
		"xpos"					"c276"	[$WIN32WIDE]//292
		"xpos"					"r102"	[!$WIN32WIDE]//102
		"ypos"					"361" //196
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"39"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	"SldFOVBC"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldFOVBC"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"128"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"1"
		"maxValue"				"180"
		"stepSize"				"1"
		"conCommand"			"cl_viewmodelfovsurvivor"
		"inverseFill"			"0"
		"navUp"				"SldGameInstructor"
		"navDown"			"Flashlightconstant"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"  臂长"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"Flashlightconstant"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"Flashlightconstant"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"147"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"// 最小值
		"maxValue"				"1"// 最大值
		"stepSize"				"1"
		"conCommand"			"r_flashlightconstant"
		"inverseFill"			"0"
		"navUp"				"SldFOVBC"
		"navDown"			"Shadow"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"光亮度"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
//	"ImgShadow"
//	{
//		"ControlName"			"ImagePanel"
//		"fieldName"				"ImgShadow"
//		"xpos"					"c282"	[$WIN32WIDE]
//		"xpos"					"r102"	[!$WIN32WIDE]
//		"ypos"					"323"
//		"wide"					"10"
//		"tall"					"10"
//		"visible"				"1"
//		"enabled"				"1"
//		"image"					""
//		"scaleimage"				"1"
//		"zpos"					"2"
//		//drawcolor_special_event_autoreplace
//	}
	"Shadow"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"Shadow"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"166"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"// 最小值
		"maxValue"				"3000"// 最大值
		"stepSize"				"1"
		"conCommand"			"cl_max_shadow_renderable_dist"
		"inverseFill"			"0"
		"navUp"				"Flashlightconstant"
		"navDown"			"Flashlightfov"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"光影子"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
//	"ImgFlashlightfov"
//	{
//		"ControlName"			"ImagePanel"
//		"fieldName"				"ImgFlashlightfov"
//		"xpos"					"c282"	[$WIN32WIDE]
//		"xpos"					"r102"	[!$WIN32WIDE]
//		"ypos"					"323"
//		"wide"					"10"
//		"tall"					"10"
//		"visible"				"1"
//		"enabled"				"1"
//		"image"					""
//		"scaleimage"				"1"
//		"zpos"					"2"
//		//drawcolor_special_event_autoreplace
//	}
	"Flashlightfov" //光射角锁100
	{
		"ControlName"			"SliderControl"
		"fieldName"				"Flashlightfov"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"185"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"100"// 最小值
		"maxValue"				"200"// 与“修复黑块”共用参数，保持一致的上限
		"stepSize"				"1"
		"conCommand"			"r_flashlightfov"
		"inverseFill"			"0"
		"navUp"				"Shadow"
		"navDown"			"GuangSheJiao"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"		
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"光射角"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"GuangSheJiao"//光射角可调节
	{
		"ControlName"			"SliderControl"
		"fieldName"				"GuangSheJiao"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"204"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"50"
		"maxValue"				"200"
		"stepSize"				"1"
		"navUp"					"Flashlightfov"
		"navDown"				"Far"
		"conCommand"			"r_flashlightfov"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"修复黑块"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"Far"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"Far"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"223"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"// 最小值
		"maxValue"				"10000"// 最大值
		"stepSize"				"1"
		"navUp"					"GuangSheJiao"
		"navDown"				"JueSeLunKuo"
		"conCommand"			"r_farz"
		"inverseFill"			"0"
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"渲染距离"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
"JueSeLunKuo"//角色轮廓
	{
		"ControlName"			"SliderControl"
		"fieldName"				"JueSeLunKuo"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"242"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"navUp"					"Far"
		"navDown"				"WuPinLunKuo"
		"conCommand"			"sv_disable_glow_survivors"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"角色轮廓"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}

	"WuPinLunKuo"//物品轮廓
	{
		"ControlName"			"SliderControl"
		"fieldName"				"WuPinLunKuo"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"261"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"navUp"					"JueSeLunKuo"
		"navDown"				"Flashlightfar"
		"conCommand"			"sv_disable_glow_faritems"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"物品轮廓"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	//"STQC"//尸体限制
	//{
	//	"ControlName"			"SliderControl"
	//	"fieldName"				"STQC"
	//	"xpos"					"c86"	[$WIN32WIDE]
	//	"xpos"					"r98"	[!$WIN32WIDE]
	//	"ypos"					"467"
	//	"zpos"					"3"
	//	"wide"					"97"// 滑块宽度
	//	"tall"					"2"// 滑块高度
	//	"visible"				"1"
	//	"enabled"				"1"
	//	"tabPosition"			"0"
	//	"minValue"				"0"
	//	"maxValue"				"50"
	//	"stepSize"				"1"
	//	"navUp"					""
	//	"navDown"				""
	//	"conCommand"			"cl_ragdoll_maxcount"
	//	"inverseFill"			"0"

		//button and label
	//	"BtnDropButton"
	//	{
	//		"ControlName"			"L4D360HybridButton"
	//		"fieldName"				"BtnDropButton"
	//		"tall"					"15"
	//		"visible"				"1"
	//		"enabled"				"1"
	//		"labelText"				"尸体限制"
	//		"style"					"smallbutton"
	//		"ActivationType"		"1"
	//		"OnlyActiveUser"		"1"
	//	}
	//}
	"Flashlightfar"
	{
		"ControlName"			"SliderControl"
		"fieldName"				"Flashlightfar"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"280"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"820"// 最小值
		"maxValue"				"3000"// 最大值
		"stepSize"				"1"
		"conCommand"			"r_flashlightfar"
		"inverseFill"			"0"
		"navUp"				"WuPinLunKuo"
		"navDown"			"SldFOV"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"光射程"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"BtnReturnToGame"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnReturnToGame"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"218"	//was 135
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"1"
		"navRight"				"SldGameVolume"
		"navUp"					"DrpGameInstructorHint"
		"navDown"				"BtnGoIdle"
		"wrap"					"1"
		"labelText"				"#L4D360UI_InGameMainMenu_ReturnToGame"
		"tooltiptext"			"#L4D360UI_InGameMainMenu_ReturnToGame_Tip"
		"style"					"MainMenuButton"
		"command"				"ReturnToGame"	// was ReturnToGame
		"ActivationType"		"1"
		"zpos"				"3"
	}
	"BtnGoIdle"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnGoIdle"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"243"	//was 160
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"1"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnReturnToGame"
		"navDown"				"BtnCallAVote"
		"labelText"				"#L4D360UI_InGameMainMenu_GoIdle"
		"tooltiptext"			"#L4D360UI_InGameMainMenu_GoIdle_Tip"
		"disabled_tooltiptext"	"#L4D360UI_InGameMainMenu_GoIdle_Disabled"
		"style"					"MainMenuButton"
		"command"				"GoIdle"
		"ActivationType"		"1"
		"zpos"				"3"
	}
	"BtnCallAVote"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnCallAVote"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"268"	//was 180
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnGoIdle"
		"navDown"				"BtnInviteFriends"
		"labelText"				"#L4D360UI_InGameMainMenu_CallAVote"
		"tooltiptext"			"#L4D360UI_InGameMainMenu_CallAVote_Tip"
		"disabled_tooltiptext" "#L4D360UI_InGameMainMenu_CallAVote_Tip"
		"style"					"MainMenuButton"
		"command" 				"FlmVoteFlyout"
		"ActivationType"		"1"
		"zpos"				"3"
	}
	"BtnInviteFriends"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnInviteFriends"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"293"	// was 210
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnCallAVote"
		"navDown"				"BtnLeaderboard"
		"labelText"				"#L4D360UI_Lobby_InviteFriends"
		"tooltiptext"			"#L4D360UI_Lobby_InviteFriends_Tip"	
		"style"					"MainMenuButton"
		"ActivationType"		"1"
		"zpos"				"3"
		"command"				"InviteUI_Steam"
	}
	"BtnLeaderboard"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnLeaderboard"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"318"	//was 235
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"	
		"autoResize"			"1"		
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnInviteFriends"
		"navDown"				"BtnStatsAndAchievements"
		"labelText"				"#L4D360UI_Leaderboard_Title"
		"tooltiptext"			"#L4D360UI_MainMenu_SurvivalLeaderboards_Tip"
		"style"					"MainMenuButton"
		"command"				"Leaderboards_"
		"ActivationType"		"1"
		"zpos"				"3"
	}
	"BtnStatsAndAchievements"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnStatsAndAchievements"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"343"	//was 260
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnLeaderboard"
		"navDown"				"BtnAddons"
		"labelText"				"#L4D360UI_MainMenu_StatsAndAchievements"
		"tooltiptext"			"#L4D360UI_MainMenu_PCStatsAndAchievements_Tip"	
		"style"					"MainMenuButton"
		"command"				"StatsAndAchievements"
		"ActivationType"		"1"
		"zpos"				"3"
	}
	// "IconAddons"
	// {
		// "ControlName"			"ImagePanel"
		// "fieldName"				"IconAddons"
		// "xpos"					"c-304"	[$WIN32WIDE]
		// "xpos"					"80"	[!$WIN32WIDE]
		// "ypos"					"252"
		// "wide"					"15"
		// "tall"					"15"
		// "scaleImage"			"1"
		// "pinCorner"				"0"
		// "visible"				"1"
		// "enabled"				"1"
		// "tabPosition"			"0"
		// "image"					"addons"
		// "frame"					"0"
		// "scaleImage"			"1"
	// }	
	"BtnAddons"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnAddons"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"368"
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnStatsAndAchievements"
		"navDown"				"BtnAudio1"
		"tooltiptext"			"#L4D360UI_Extras_Addons_Tip"
		"labelText"				"第三方附件"  [!$RUSSIAN]
		"style"					"MainMenuButton"
		"command"				"Addons"
		"ActivationType"		"1"
		"allcaps"			"1" // Urik: to ensure caps'd letters
		"zpos"				"3"
	}
	"BtnAudio1"	
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnAudio1"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"393"
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnAddons"
		"navDown"				"BtnOptions"
		"tooltiptext"			"#L4D_Audio_tip"
		"labelText"				"#GameUI_Audio"
		"style"					"MainMenuButton"
		"command"				"Audio"
		"allcaps"				"1"
		"zpos"				"3"
	}	
	"BtnOptions"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnOptions"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"418"
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnAudio1"
		"navDown"				"BtnExitToMainMenu"
		"labelText"				"#L4D360UI_MainMenu_Options"
		"tooltiptext"			"#L4D360UI_MainMenu_Options_Tip"
		"style"					"MainMenuButton"
		"command"				"FlmOptionsFlyout"
		"ActivationType"		"1"
		"zpos"				"3"
	}
	"BtnExitToMainMenu"
	{
		"ControlName"			"L4D360HybridButton"
		"fieldName"				"BtnExitToMainMenu"
		"xpos"					"12"	[$WIN32WIDE]
		"xpos"					"12"	[!$WIN32WIDE]
		"ypos"					"443"	// was 322
		"wide"					"184"	[$ENGLISH || $RUSSIAN || $JAPANESE || $KOREAN || $KOREANA || $SCHINESE || $TCHINESE]
		"wide"					"184"	[!$RUSSIAN && !$ENGLISH && !$JAPANESE && !$KOREAN && !$KOREANA && !$SCHINESE && !$TCHINESE]
		"tall"					"20"
		"autoResize"			"1"
		"pinCorner"				"0"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"navRight"				"SldGameVolume"
		"navUp"					"BtnOptions"
		"navDown"				"DrpCrosshair"
		"labelText"				"#L4D360UI_InGameMainMenu_ExitToMainMenu"
		"tooltiptext"			"#L4D360UI_InGameMainMenu_ExitToMainMenu_Tip"
		"style"					"MainMenuButton"
		"command"				"ExitToMainMenu"
		"ActivationType"		"1"
		"zpos"				"3"
	}
	"FlmOptionsFlyout"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmOptionsFlyout"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"3"
		"InitialFocus"			"BtnVideo" 
		"resourceFile"			"resource/UI/L4D360UI/OptionsFlyout.res"		
	}
	"FlmOptionsGuestFlyout"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmOptionsGuestFlyout"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"3"
		"InitialFocus"			"BtnAudioVideo"
		"resourceFile"			"resource/UI/L4D360UI/OptionsGuestFlyout.res"
	}
	"FlmVoteFlyout"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmVoteFlyout"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"3"
		"InitialFocus"			"BtnReturnToLobby"
		"resourceFile"			"resource/UI/L4D360UI/InGameVoteFlyout.res"
	}
	"FlmVoteFlyoutVersus"
	{
		"ControlName"		"FlyoutMenu"
		"fieldName"			"FlmVoteFlyoutVersus"
		"visible"			"0"
		"wide"				"0"
		"tall"				"0"
		"zpos"				"3"
		"InitialFocus"		"BtnReturnToLobby"
		"resourceFile"		"resource/UI/L4D360UI/InGameVoteFlyoutVersus.res"
	}
	"FlmVoteFlyoutSurvival"
	{
		"ControlName"		"FlyoutMenu"
		"fieldName"			"FlmVoteFlyoutSurvival"
		"visible"			"0"
		"wide"				"0"
		"tall"				"0"
		"zpos"				"3"
		"InitialFocus"		"BtnReturnToLobby"
		"resourceFile"		"resource/UI/L4D360UI/InGameVoteFlyoutSurvival.res"
	}
	"FlmCrosshair"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmCrosshair"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"4"
		"InitialFocus"			"SldRed"
		"resourceFile"			"resource/UI/L4D360UI/dropdownCrosshair.res"
		"OnlyActiveUser"		"0"
	}
	"FlmNetGraph"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmNetGraph"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"4"
		"InitialFocus"			"SldMode"
		"resourceFile"			"resource/UI/L4D360UI/DropDownNetGraph.res"
		"OnlyActiveUser"		"1"
	}
	"FlmSplitScreenMode"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmSplitScreenMode"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"4"
		"InitialFocus"			"SldMode"
		"resourceFile"			"resource/UI/L4D360UI/DropDownSplitScreenMode.res"
		"OnlyActiveUser"		"1"
	}
	"FlmCaptionsHint"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmCaptionsHint"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"4"
		"InitialFocus"			"SldMode"
		"resourceFile"			"resource/UI/L4D360UI/DropDown_captionshint.res"
		"OnlyActiveUser"		"1"
	}
	"FlmGameInstructorHint"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmGameInstructorHint"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"4"
		"InitialFocus"			"SldMode"
		"resourceFile"			"resource/UI/L4D360UI/DropDown_InstructorSliderHint.res"
		"OnlyActiveUser"		"1"
	}
	"FlmTvGammaHint"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmTvGammaHint"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"4"
		"InitialFocus"			"SldMode"
		"resourceFile"			"resource/UI/L4D360UI/DropDown_tvgammaHint.res"
		"OnlyActiveUser"		"1"
	}
	"FlmFAQ"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"FlmFAQ"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"4"
		"InitialFocus"			"PnlBackground"
		"resourceFile"			"resource/UI/L4D360UI/DropDownSlidersFAQ.res"
		"OnlyActiveUser"		"1"
	}
	"WeatherControl"
	{
		"ControlName"			"FlyoutMenu"
		"fieldName"				"WeatherControl"
		"visible"				"0"
		"wide"					"0"
		"tall"					"0"
		"zpos"					"4"
		"InitialFocus"			"SldMode"
		"resourceFile"			"resource/UI/L4D360UI/dropdownWeatherControl.res"
		"OnlyActiveUser"		"0"
	}









"ImgFOV"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgFOV"
		"xpos"					"c276"	[$WIN32WIDE]//292
		"xpos"					"r102"	[!$WIN32WIDE]//102
		"ypos"					"361" //196
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"39"
		"scaleimage"				"1"
		"zpos"					"2"
	}	
	"ImgFOV2"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgFOV2"
		"xpos"					"c288"	[$WIN32WIDE]//304
		"xpos"					"r102"	[!$WIN32WIDE]//102
		"ypos"					"353"//188
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"44"
		"scaleimage"				"1"
		"zpos"					"2"
	}	
	"SldFOV"//第一人称视场的数据条
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldFOV"
		"xpos"					"c-92"	[$WIN32WIDE]//296
		"xpos"					"c-92"	[!$WIN32WIDE]//98
		"ypos"					"299"//199
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"125"
		"stepSize"				"0.1"
		"conCommand"			"fov_desired"
		"inverseFill"			"0"
		"navUp"				"Flashlightfar"
		"navDown"			"SldCamDist"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"第一视场"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}	
		

	"ImgCamDist"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgCamDist"
		"xpos"					"c276"	[$WIN32WIDE]//292
		"xpos"					"r102"	[!$WIN32WIDE]//102
		"ypos"					"346"//181
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"39"
		"scaleimage"				"1"
		"zpos"					"2"
	}	
	"ImgCamDist2"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"ImgCamDist2"
		"xpos"					"c288"	[$WIN32WIDE]//304
		"xpos"					"r102"	[!$WIN32WIDE]//102
		"ypos"					"338"//173
		"wide"					"10"
		"tall"					"10"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"43"
		"scaleimage"				"1"
		"zpos"					"2"
	}	
	

"SldCamDist"    //第三人称视场的数据条
	{
		"ControlName"			"SliderControl"
		"fieldName"				"SldCamDist"
		"xpos"					"c-92"	[$WIN32WIDE]//296
		"xpos"					"c-92"	[!$WIN32WIDE]//98
		"ypos"					"318"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"19900"
		"stepSize"				"20"
		"conCommand"			"cam_idealdist"
		"inverseFill"			"0"
		"navUp"				"SldFOV"
		"navDown"			"c_maxdistance"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"第三人称距离"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	
		"Imgmaxdistance"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Imgmaxdistance"
		"xpos"					"c16"	[$WIN32WIDE]
		"xpos"					"r98"	[!$WIN32WIDE]
		"ypos"					"443"
		"wide"					"12"
		"tall"					"12"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"43"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	
		"c_maxdistance"    //第三人称视场上限
	{
		"ControlName"			"SliderControl"
		"fieldName"				"c_maxdistance"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"337"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"19980"
		"maxValue"				"19990"
		"stepSize"				"10" //50
		"inverseFill"			"0"
		"conCommand"			"c_maxdistance"
		"inverseFill"			"0"
		"navUp"				"SldCamDist"
		"navDown"			"c_thirdpersonshoulderheight"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"视上限"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	
	"Imgthirdpersonshoulderheight"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Imgthirdpersonshoulderheight"
		"xpos"					"c16"	[$WIN32WIDE]
		"xpos"					"r98"	[!$WIN32WIDE]
		"ypos"					"404"//415
		"wide"					"12"
		"tall"					"12"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"43"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	
	"c_thirdpersonshoulderheight"    //第三人称高度的数据条
	{
		"ControlName"			"SliderControl"
		"fieldName"				"c_thirdpersonshoulderheight"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"356"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"-600"
		"maxValue"				"600"
		"stepSize"				"5" //50
		"inverseFill"			"0"
		"conCommand"			"c_thirdpersonshoulderheight"
		"inverseFill"			"0"
		"navUp"				"c_maxdistance"
		"navDown"			"c_thirdpersonshoulderheight-"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"视高度"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	
	"Imgthird-"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Imgthirdpersonshoulderheight"
		"xpos"					"c-84"	[$WIN32WIDE]
		"xpos"					"r98"	[!$WIN32WIDE]
		"ypos"					"415"
		"wide"					"12"
		"tall"					"12"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"43"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	
	"c_thirdpersonshoulderheight-"    //第三人称左的数据条
	{
		"ControlName"			"SliderControl"
		"fieldName"				"c_thirdpersonshoulderheight-"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"375"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"-1000"
		"maxValue"				"0"
		"stepSize"				"20" //50
		"inverseFill"			"0"
		"conCommand"			"c_thirdpersonshoulderoffset"
		"inverseFill"			"0"
		"navUp"				"c_thirdpersonshoulderheight"
		"navDown"			"thirdpersonshoulderoffset+"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"视左移"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	
	"Imgthird+"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Imgthird+"
		"xpos"					"c16"	[$WIN32WIDE]
		"xpos"					"r98"	[!$WIN32WIDE]
		"ypos"					"415"
		"wide"					"12"
		"tall"					"12"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"43"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	
	"thirdpersonshoulderoffset+"    //第三人称右移的数据条
	{
		"ControlName"			"SliderControl"
		"fieldName"				"thirdpersonshoulderoffset+"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"394"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1000"
		"stepSize"				"20" //50
		"inverseFill"			"0"
		"conCommand"			"c_thirdpersonshoulderoffset"
		"inverseFill"			"0"
		"navUp"				"c_thirdpersonshoulderheight-"
		"navDown"			"cam_idealyaw"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"视右移"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	
	"Imgidealyaw"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Imgidealyaw"
		"xpos"					"c-84"	[$WIN32WIDE]
		"xpos"					"r98"	[!$WIN32WIDE]
		"ypos"					"402"
		"wide"					"12"
		"tall"					"12"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"43"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	
	"cam_idealyaw"    //第三人称角度的数据条
	{
		"ControlName"			"SliderControl"
		"fieldName"				"cam_idealyaw"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"413"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"360"
		"stepSize"				"1" //50
		"inverseFill"			"0"
		"conCommand"			"cam_idealyaw"
		"inverseFill"			"0"
		"navUp"				"thirdpersonshoulderoffset+"
		"navDown"			"c_maxyaw"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"环视角"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	
	"Imgmaxyaw"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Imgmaxyaw"
		"xpos"					"c16"	[$WIN32WIDE]
		"xpos"					"r98"	[!$WIN32WIDE]
		"ypos"					"454"//184
		"wide"					"12"
		"tall"					"12"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"43"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	
	"c_maxyaw"    //第三人称角度的数据条
	{
		"ControlName"			"SliderControl"
		"fieldName"				"c_maxyaw"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"432"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"360"
		"maxValue"				"360"
		"stepSize"				"1" //50
		"inverseFill"			"0"
		"conCommand"			"c_maxyaw"
		"inverseFill"			"0"
		"navUp"				"cam_idealyaw"
		"navDown"			"cam_collision"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"环上限"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	
	"Imgcollision"
	{
		"ControlName"			"ImagePanel"
		"fieldName"				"Imgcollision"
		"xpos"					"c-84"	[$WIN32WIDE]
		"xpos"					"r98"	[!$WIN32WIDE]
		"ypos"					"454"//184
		"wide"					"12"
		"tall"					"12"
		"visible"				"0"
		"enabled"				"1"
		"image"					"../vgui/icon_64x64"
		"frame"					"43"
		"scaleimage"				"1"
		"zpos"					"2"
	}
	
	"cam_collision"    //第三人称碰撞的数据条
	{
		"ControlName"			"SliderControl"
		"fieldName"				"cam_collision"
		"xpos"					"c-92"	[$WIN32WIDE]
		"xpos"					"c-92"	[!$WIN32WIDE]
		"ypos"					"451"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"0"
		"stepSize"				"1" //50
		"inverseFill"			"0"
		"conCommand"			"cam_collision"
		"inverseFill"			"0"
		"navUp"				"c_maxyaw"
		"navDown"			"SldGameVolume"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"视碰撞"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	
		"hidehud"    //隐藏界面
	{
		"ControlName"			"SliderControl"
		"fieldName"				"hidehud"
		"xpos"					"r196"	[$WIN32WIDE]
		"xpos"					"r196"	[!$WIN32WIDE]
		"ypos"					"14"
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"4"
		"stepSize"				"1" //50
		"inverseFill"			"0"
		"conCommand"			"hidehud"
		"inverseFill"			"0"
		"navUp"				"ShiTiXianZhi"
		"navDown"			"DaoYanXiTong"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"隐藏界面"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}

"DaoYanXiTong"//导演系统
	{
		"ControlName"			"SliderControl"
		"fieldName"				"DaoYanXiTong"
		"xpos"					"r196"	[$WIN32WIDE]
		"xpos"					"r196"	[!$WIN32WIDE]
		"ypos"					"33"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"// 最小值
		"maxValue"				"1"// 最大值
		"stepSize"				"1"
		"conCommand"			"director_show_intensity"
		"inverseFill"			"0"
		"navUp"				"hidehud"
		"navDown"			"DiTuQuanLiang"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"导演系统"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
		
		
	}

"DiTuQuanLiang"//地图全亮
	{
		"ControlName"			"SliderControl"
		"fieldName"				"DiTuQuanLiang"
		"xpos"					"r196"	[$WIN32WIDE]//296
		"xpos"					"r196"	[!$WIN32WIDE]//98
		"ypos"					"52"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"navUp"					"DaoYanXiTong"
		"navDown"				"KaiQiangDouPing"
		"conCommand"			"mat_fullbright"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"地图全亮"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}

"KaiQiangDouPing"//开枪抖屏
	{
		"ControlName"			"SliderControl"
		"fieldName"				"KaiQiangDouPing"
		"xpos"					"r196"	[$WIN32WIDE]//296
		"xpos"					"r196"	[!$WIN32WIDE]//98
		"ypos"					"71"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"0"  //0不抖屏
		"stepSize"				"1"
		"navUp"					"DiTuQuanLiang"
		"navDown"				"KaiQiangShanGuang"
		"conCommand"			"z_gun_vertical_punch"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"开枪抖屏"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}

	"KaiQiangShanGuang"//开枪闪光
	{
		"ControlName"			"SliderControl"
		"fieldName"				"KaiQiangShanGuang"
		"xpos"					"r196"	[$WIN32WIDE]//296
		"xpos"					"r196"	[!$WIN32WIDE]//98
		"ypos"					"90"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"0" //0不闪光
		"stepSize"				"1"
		"navUp"					"KaiQiangDouPing"
		"navDown"				"DongTaiShouDian"
		"conCommand"			"r_flashlightmuzzleflash"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"开枪闪光"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"DongTaiShouDian"//动态手电(beam_flashlight.vtf需要变透明)
	{
		"ControlName"			"SliderControl"
		"fieldName"				"DongTaiShouDian"
		"xpos"					"r196"	[$WIN32WIDE]//296
		"xpos"					"r196"	[!$WIN32WIDE]//98
		"ypos"					"109"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"0"
		"stepSize"				"0"
		"navUp"					"KaiQiangShanGuang"
		"navDown"				"DaoHangWangGe"
		"conCommand"			"r_flashlight_attach_to_viewmodel"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"动态手电"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
"DaoHangWangGe"//导航网格
	{
		"ControlName"			"SliderControl"
		"fieldName"				"DaoHangWangGe"
		"xpos"					"r196"	[$WIN32WIDE]//286
		"xpos"					"r196"	[!$WIN32WIDE]
		"ypos"					"128"
		"zpos"					"3"
		"wide"					"184"// 滑块宽度
		"tall"					"15"// 滑块高度
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"navUp"					"DongTaiShouDian"
		"navDown"				"XianShiZhangAi"
		"conCommand"			"nav_edit"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"导航网格"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}

	"XianShiZhangAi"//显示障碍
	{
		"ControlName"			"SliderControl"
		"fieldName"				"XianShiZhangAi"
		"xpos"					"r196"	[$WIN32WIDE]//286
		"xpos"					"r196"	[!$WIN32WIDE]//98
		"ypos"					"147"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"2"
		"stepSize"				"1"
		"navUp"					"DaoHangWangGe"
		"navDown"				"WuQianZhi"
		"conCommand"			"r_drawclipbrushes"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"显示障碍"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"WuQianZhi"//雾前置
	{
		"ControlName"			"SliderControl"
		"fieldName"				"WuQianZhi"
		"xpos"					"r196"	[$WIN32WIDE]//286
		"xpos"					"r196"	[!$WIN32WIDE]//98
		"ypos"					"166"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"navUp"					"XianShiZhangAi"
		"navDown"				"Wu"
		"conCommand"			"fog_override"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"迷雾关闭"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}
	"Wu"//雾
	{
		"ControlName"			"SliderControl"
		"fieldName"				"Wu"
		"xpos"					"r196"	[$WIN32WIDE]//286
		"xpos"					"r196"	[!$WIN32WIDE]//98
		"ypos"					"185"//184
		"zpos"					"3"
		"wide"					"184"//slider_width
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"navUp"					"WuQianZhi"
		"navDown"				"Expanded_SldRed"
		"conCommand"			"fog_enable"
		"inverseFill"			"0"

		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"tall"					"15"
			"visible"				"1"
			"enabled"				"1"
			"labelText"				"雾气开启"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"
		}
	}

	// Expanded controls and requested defaults.
	"Expanded_SldRed"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldRed"
		"xpos"					"r196"//sliderxpos
		"ypos"					"204"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"255"
		"stepSize"				"25"
		"conCommand"			"cl_crosshair_red"
		"inverseFill"			"0"
		"navUp"				"Wu"
		"navDown"			"Expanded_SldGreen"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"准星红色"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldGreen"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldGreen"
		"xpos"					"r196"//sliderxpos
		"ypos"					"223"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"255"
		"stepSize"				"25"
		"conCommand"			"cl_crosshair_green"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldRed"
		"navDown"			"Expanded_SldBlue"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"准星绿色"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldBlue"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldBlue"
		"xpos"					"r196"//sliderxpos
		"ypos"					"242"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"255"
		"stepSize"				"25"
		"conCommand"			"cl_crosshair_blue"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldGreen"
		"navDown"			"Expanded_SldAlpha"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"准星蓝色"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldAlpha"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldAlpha"
		"xpos"					"r196"//sliderxpos
		"ypos"					"261"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"255"
		"stepSize"				"25"
		"conCommand"			"cl_crosshair_alpha"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldBlue"
		"navDown"			"Expanded_SldThickness"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"准星透明度"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldThickness"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldThickness"
		"xpos"					"r196"//sliderxpos
		"ypos"					"280"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"1"
		"maxValue"				"5"
		"stepSize"				"1"
		"conCommand"			"cl_crosshair_thickness"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldAlpha"
		"navDown"			"Expanded_SldDynamic"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"准星粗细"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldDynamic"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldDynamic"
		"xpos"					"r196"//sliderxpos
		"ypos"					"299"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabPosition"			"0"
		"minValue"				"0"
		"maxValue"				"2"
		"stepSize"				"2"
		"conCommand"			"cl_crosshair_dynamic"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldThickness"
		"navDown"			"Expanded_SldMode"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"动态准星"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldMode"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldMode"
		"xpos"					"r196"//sliderxpos
		"ypos"					"318"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabRate"			"0"
		"minValue"				"0"
		"maxValue"				"4"
		"stepSize"				"1"
		"conCommand"			"net_graph"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldDynamic"
		"navDown"			"Expanded_SldHeight"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"网络参数图"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldHeight"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldHeight"
		"xpos"					"r196"//sliderxpos
		"ypos"					"337"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabRate"			"0"
		"minValue"				"0"
		"maxValue"				"620" // 720p profile: keep network text inside the viewport
		"stepSize"				"1"
		"conCommand"			"net_graphheight"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldMode"
		"navDown"			"Expanded_SldPosition"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"网络图高度"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldPosition"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldPosition"
		"xpos"					"r196"//sliderxpos
		"ypos"					"356"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabRate"			"0"
		"minValue"				"0"
		"maxValue"				"500"
		"stepSize"				"1"
		"conCommand"			"net_graphpos"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldHeight"
		"navDown"			"Expanded_SldProportionalFont"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"网络图位置"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldProportionalFont"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldProportionalFont"
		"xpos"					"r196"//sliderxpos
		"ypos"					"375"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabRate"			"0"
		"minValue"				"0"
		"maxValue"				"2"
		"stepSize"				"2"
		"conCommand"			"net_graphproportionalfont"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldPosition"
		"navDown"			"Expanded_SldShowInterp"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"网络图字体"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SldShowInterp"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SldShowInterp"
		"xpos"					"r196"//sliderxpos
		"ypos"					"394"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabRate"			"0"
		"minValue"				"0"
		"maxValue"				"2"
		"stepSize"				"2"
		"conCommand"			"net_graphshowinterp"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldProportionalFont"
		"navDown"			"Expanded_RainParticleDensity"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"网络图色条"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_RainParticleDensity"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_RainParticleDensity"
		"xpos"					"r196"//sliderxpos
		"ypos"					"413"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabRate"				"0"
		"minValue"				"0"
		"maxValue"				"1"
		"stepSize"				"1"
		"conCommand"			"r_RainParticleDensity"
		"inverseFill"			"0"
		"navUp"				"Expanded_SldShowInterp"
		"navDown"			"Expanded_SnowParticles"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"雨量"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"Expanded_SnowParticles"
	{
		"ControlName"			"SliderControl"
		"fieldName" "Expanded_SnowParticles"
		"xpos"					"r196"//sliderxpos
		"ypos"					"432"
		"zpos"					"3"
		"wide"					"184"//sliderwidth
		"tall"					"15"
		"visible"				"1"
		"enabled"				"1"
		"tabRate"				"0"
		"minValue"				"0"
		"maxValue"				"800"
		"stepSize"				"1"
		"conCommand"			"r_SnowParticles"
		"inverseFill"			"0"
		"navUp"				"Expanded_RainParticleDensity"
		"navDown"			"ShiTiXianZhi"
		//button and label
		"BtnDropButton"
		{
			"ControlName"			"L4D360HybridButton"
			"fieldName"				"BtnDropButton"
			"visible"				"1"
			"enabled"				"1"
			"labeltext"				"雪量"
			"style"					"smallbutton"
			"ActivationType"		"1"
			"OnlyActiveUser"		"1"

		}
	}
	"ShiTiXianZhi"
	{
		"zpos" "3"
		"navup" "Expanded_SnowParticles"
		"navdown" "hidehud"
		"ControlName" "SliderControl"
		"fieldName" "ShiTiXianZhi"
		"xpos" "r196"
		"ypos" "451"
		"wide" "184"
		"tall" "15"
		"visible" "1"
		"enabled" "1"
		"minValue" "0"
		"maxValue" "75"
		"stepSize" "1"
		"conCommand" "cl_ragdoll_maxcount"
		"inverseFill" "0"
		"BtnDropButton"
		{
			"ControlName" "L4D360HybridButton"
			"fieldName" "BtnDropButton"
			"tall" "15"
			"visible" "1"
			"enabled" "1"
			"labelText" "尸体数量"
			"style" "SmallButton"
			"ActivationType" "1"
			"OnlyActiveUser" "1"
		}
	}
	"Init_fog_enable"
	{
		"mouseinputenabled" "0"
		"keyboardsinputenabled" "0"
		"ControlName" "SliderControl"
		"fieldName" "Init_fog_enable"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "0"
		"maxValue" "0"
		"stepSize" "1"
		"conCommand" "fog_enable"
		"inverseFill" "0"
		"BtnDropButton"
		{
			"ControlName" "L4D360HybridButton"
			"fieldName" "BtnDropButton"
			"tall" "15"
			"visible" "1"
			"enabled" "1"
			"labelText" ""
			"style" "SmallButton"
			"ActivationType" "1"
			"OnlyActiveUser" "1"
		}
	}
	"Init_cl_ragdoll_maxcount"
	{
		"mouseinputenabled" "0"
		"keyboardsinputenabled" "0"
		"ControlName" "SliderControl"
		"fieldName" "Init_cl_ragdoll_maxcount"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "0"
		"maxValue" "0"
		"stepSize" "1"
		"conCommand" "cl_ragdoll_maxcount"
		"inverseFill" "0"
		"BtnDropButton"
		{
			"ControlName" "L4D360HybridButton"
			"fieldName" "BtnDropButton"
			"tall" "15"
			"visible" "1"
			"enabled" "1"
			"labelText" ""
			"style" "SmallButton"
			"ActivationType" "1"
			"OnlyActiveUser" "1"
		}
	}
	"Init_sv_disable_glow_survivors"
	{
		"mouseinputenabled" "0"
		"keyboardsinputenabled" "0"
		"ControlName" "SliderControl"
		"fieldName" "Init_sv_disable_glow_survivors"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "0"
		"maxValue" "0"
		"stepSize" "1"
		"conCommand" "sv_disable_glow_survivors"
		"inverseFill" "0"
		"BtnDropButton"
		{
			"ControlName" "L4D360HybridButton"
			"fieldName" "BtnDropButton"
			"tall" "15"
			"visible" "1"
			"enabled" "1"
			"labelText" ""
			"style" "SmallButton"
			"ActivationType" "1"
			"OnlyActiveUser" "1"
		}
	}
	"Init_sv_disable_glow_faritems"
	{
		"mouseinputenabled" "0"
		"keyboardsinputenabled" "0"
		"ControlName" "SliderControl"
		"fieldName" "Init_sv_disable_glow_faritems"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "0"
		"maxValue" "0"
		"stepSize" "1"
		"conCommand" "sv_disable_glow_faritems"
		"inverseFill" "0"
		"BtnDropButton"
		{
			"ControlName" "L4D360HybridButton"
			"fieldName" "BtnDropButton"
			"tall" "15"
			"visible" "1"
			"enabled" "1"
			"labelText" ""
			"style" "SmallButton"
			"ActivationType" "1"
			"OnlyActiveUser" "1"
		}
	}
	"Init_r_flashlightconstant"
	{
		"mouseinputenabled" "0"
		"keyboardsinputenabled" "0"
		"ControlName" "SliderControl"
		"fieldName" "Init_r_flashlightconstant"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "1"
		"maxValue" "1"
		"stepSize" "1"
		"conCommand" "r_flashlightconstant"
		"inverseFill" "0"
		"BtnDropButton"
		{
			"ControlName" "L4D360HybridButton"
			"fieldName" "BtnDropButton"
			"tall" "15"
			"visible" "1"
			"enabled" "1"
			"labelText" ""
			"style" "SmallButton"
			"ActivationType" "1"
			"OnlyActiveUser" "1"
		}
	}
	"Init_r_flashlightfar"
	{
		"mouseinputenabled" "0"
		"keyboardsinputenabled" "0"
		"ControlName" "SliderControl"
		"fieldName" "Init_r_flashlightfar"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "3000"
		"maxValue" "3000"
		"stepSize" "1"
		"conCommand" "r_flashlightfar"
		"inverseFill" "0"
		"BtnDropButton"
		{
			"ControlName" "L4D360HybridButton"
			"fieldName" "BtnDropButton"
			"tall" "15"
			"visible" "1"
			"enabled" "1"
			"labelText" ""
			"style" "SmallButton"
			"ActivationType" "1"
			"OnlyActiveUser" "1"
		}
	}
	"Init_r_flashlightfov"
	{
		"mouseinputenabled" "0"
		"keyboardsinputenabled" "0"
		"ControlName" "SliderControl"
		"fieldName" "Init_r_flashlightfov"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "200"
		"maxValue" "200"
		"stepSize" "1"
		"conCommand" "r_flashlightfov"
		"inverseFill" "0"
		"BtnDropButton"
		{
			"ControlName" "L4D360HybridButton"
			"fieldName" "BtnDropButton"
			"tall" "15"
			"visible" "1"
			"enabled" "1"
			"labelText" ""
			"style" "SmallButton"
			"ActivationType" "1"
			"OnlyActiveUser" "1"
		}
	}
	// Network defaults for a 1280x720 viewport. Build tool adapts H-100 in memory.
	"Init_net_graph"
	{
		"ControlName" "SliderControl"
		"fieldName" "Init_net_graph"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "1"
		"maxValue" "1"
		"stepSize" "1"
		"conCommand" "net_graph"
	}
	"Init_net_graphpos"
	{
		"ControlName" "SliderControl"
		"fieldName" "Init_net_graphpos"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "1"
		"maxValue" "1"
		"stepSize" "1"
		"conCommand" "net_graphpos"
	}
	"Init_net_graphheight"
	{
		"ControlName" "SliderControl"
		"fieldName" "Init_net_graphheight"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "620"
		"maxValue" "620"
		"stepSize" "1"
		"conCommand" "net_graphheight"
	}
	"Init_net_graphproportionalfont"
	{
		"ControlName" "SliderControl"
		"fieldName" "Init_net_graphproportionalfont"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "0"
		"maxValue" "0"
		"stepSize" "1"
		"conCommand" "net_graphproportionalfont"
	}
	"Init_net_graphtext"
	{
		"ControlName" "SliderControl"
		"fieldName" "Init_net_graphtext"
		"xpos" "0"
		"ypos" "9999"
		"wide" "1"
		"tall" "1"
		"visible" "1"
		"enabled" "1"
		"minValue" "1"
		"maxValue" "1"
		"stepSize" "1"
		"conCommand" "net_graphtext"
	}
}
