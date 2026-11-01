; Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
; Randis UDS installer. Built by packaging/build_installer.py, which passes Version, Stage and OutDir.
; Installs per user with no admin rights, into a folder the app can write to: it edits its own code, so it can't be locked away.
Unicode true
; bzip2 and zlib carry the simplest licenses of NSIS's compressors
SetCompressor /SOLID bzip2
RequestExecutionLevel user

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "webview2_check.nsh"

!define APP_NAME "Randis UDS"
!define ICON "${Stage}\app\ui\logo\uds-base.ico"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\RandisUDS"

Name "${APP_NAME}"
OutFile "${OutDir}\RandisUDS-Setup-${Version}.exe"
InstallDir "$LOCALAPPDATA\Programs\RandisUDS"
ShowInstDetails nevershow
ShowUninstDetails nevershow

!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
!define MUI_WELCOMEFINISHPAGE_BITMAP "finish_side.bmp"
!define MUI_COMPONENTSPAGE_NODESC
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Open ${APP_NAME}"
!define MUI_FINISHPAGE_RUN_FUNCTION OpenApp

!define MUI_PAGE_CUSTOMFUNCTION_SHOW ComponentsTitle
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

VIProductVersion "${Version}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${Version}"
VIAddVersionKey "FileVersion" "${Version}"
VIAddVersionKey "FileDescription" "${APP_NAME} setup"
VIAddVersionKey "CompanyName" "${APP_NAME}"
VIAddVersionKey "LegalCopyright" ""

Function ComponentsTitle
  !insertmacro MUI_HEADER_TEXT "Choose what to add" "${APP_NAME} installs for this Windows user only and needs no admin rights."
FunctionEnd

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP "${APP_NAME} needs 64-bit Windows." /SD IDOK
    Abort
  ${EndIf}
  !insertmacro CheckWebView2 $0
  ${If} $0 != 1
    MessageBox MB_OK|MB_ICONINFORMATION "${APP_NAME} needs the Microsoft Edge WebView2 Runtime, which this PC does not seem to have.$\r$\nYou can get it free from Microsoft: developer.microsoft.com/microsoft-edge/webview2$\r$\nSetup will continue." /SD IDOK
  ${EndIf}
FunctionEnd

Function OpenApp
  SetOutPath "$INSTDIR\app"
  Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\app\launch.py"'
FunctionEnd

Section "${APP_NAME}" SecMain
  SectionIn RO
  ; an update: code the user's Claude edited is saved first, then the new code goes in. If saving fails, nothing is overwritten.
  ${If} ${FileExists} "$INSTDIR\python\pythonw.exe"
  ${AndIf} ${FileExists} "$INSTDIR\app\app.py"
    InitPluginsDir
    File "/oname=$PLUGINSDIR\update_backup.py" "update_backup.py"
    ExecWait '"$INSTDIR\python\pythonw.exe" "$PLUGINSDIR\update_backup.py" "$INSTDIR\app"' $2
    ${If} $2 == 3
      MessageBox MB_OK|MB_ICONINFORMATION "Code you changed was saved before updating:$\r$\n$INSTDIR\app\data\edited_before_update" /SD IDOK
    ${ElseIf} $2 != 0
      MessageBox MB_OK|MB_ICONSTOP "Setup couldn't save the code you changed, so it stopped without changing anything." /SD IDOK
      Abort
    ${EndIf}
  ${EndIf}
  SetOutPath "$INSTDIR\python"
  File /r "${Stage}\python\*"
  SetOutPath "$INSTDIR\app"
  File /r "${Stage}\app\*"
  ; what the user makes lives in data: reinstalling never overwrites it
  SetOverwrite off
  SetOutPath "$INSTDIR\app\data"
  File /r "${Stage}\user_data\*"
  SetOverwrite on

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${Version}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "${APP_NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\app\ui\logo\uds-base.ico"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1

  ; the shortcut's "start in" folder is the current output path
  SetOutPath "$INSTDIR\app"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\app\launch.py"' "$INSTDIR\app\ui\logo\uds-base.ico"
SectionEnd

; on unless the user unticks it
Section "Create a desktop shortcut" SecDesktop
  SetOutPath "$INSTDIR\app"
  ; never replace a shortcut this setup didn't make: it may open another copy. The name used goes in the registry for uninstall.
  ReadRegStr $1 HKCU "${UNINSTALL_KEY}" "DesktopShortcut"
  ${If} $1 == ""
    StrCpy $1 "${APP_NAME}"
    ${If} ${FileExists} "$DESKTOP\$1.lnk"
      StrCpy $1 "${APP_NAME} (installed)"
    ${EndIf}
  ${EndIf}
  CreateShortCut "$DESKTOP\$1.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\app\launch.py"' "$INSTDIR\app\ui\logo\uds-base.ico"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DesktopShortcut" "$1"
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\${APP_NAME}.lnk"
  ReadRegStr $1 HKCU "${UNINSTALL_KEY}" "DesktopShortcut"
  ${If} $1 != ""
    Delete "$DESKTOP\$1.lnk"
  ${EndIf}
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\app\__pycache__"
  ; only the files setup put there, written by build_installer.py: data and anything else the user made stay
  !include "${Stage}\uninstall_files.nsh"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
