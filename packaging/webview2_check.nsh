; Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
; Sets the given variable to 1 if the WebView2 Runtime looks installed. The installer is a 32-bit program, so plain SOFTWARE\Microsoft reads the
; machine-wide WOW6432Node copy. The guid can be overridden so the "not found" path can be tested on a PC that has it.
!ifndef WV2_GUID
  !define WV2_GUID "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
!endif
!macro CheckWebView2 RESULT
  StrCpy ${RESULT} 0
  ReadRegStr $R9 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  StrCmp $R9 "" +2
    StrCpy ${RESULT} 1
  ReadRegStr $R9 HKCU "Software\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  StrCmp $R9 "" +2
    StrCpy ${RESULT} 1
!macroend
