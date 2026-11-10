#ifndef AppVersion
#define AppVersion "3.7.0-preview"
#endif
[Setup]
AppId={{964D2DF7-B3B0-4F23-BB4C-87F027C94155}
AppName=Harry Translate
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\HarryTranslate
DefaultGroupName=Harry Translate
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=HarryTranslateSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\HarryTranslate.exe
LicenseFile=..\LICENSE
CloseApplications=yes

[Messages]
SetupWindowTitle=安装 - %1
SetupAppTitle=安装
WizardLicense=许可协议
LicenseLabel3=请阅读以下许可协议。必须接受协议才能继续安装。
LicenseAccepted=我接受协议(&A)
LicenseNotAccepted=我不接受协议(&D)
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonCancel=取消
ButtonFinish=完成(&F)
WizardSelectDir=选择安装位置
SelectDirLabel3=安装程序会将 [name] 安装到以下文件夹。
WizardReady=准备安装
ReadyLabel1=现在可以开始安装 [name]。
WizardInstalling=正在安装
InstallingLabel=正在将 [name] 安装到你的电脑，请稍候。
FinishedHeadingLabel=[name] 安装完成
FinishedLabelNoIcons=安装已完成。点击“完成”退出安装程序。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
Source: "..\dist\HarryTranslate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\Harry Translate"; Filename: "{app}\HarryTranslate.exe"
Name: "{userdesktop}\Harry Translate"; Filename: "{app}\HarryTranslate.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\HarryTranslate.exe"; Description: "打开 Harry Translate"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2: Boolean;
var Version: String;
begin
  Result := (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM32, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer;
begin
  Result := '';
  if not HasWebView2 then begin
    ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code) then
      Result := '无法启动微软 WebView2 安装程序，请检查 Windows 权限。'
    else if not HasWebView2 then
      Result := 'WebView2 安装失败（代码 ' + IntToStr(Code) + '）。首次安装需要联网，请检查网络后重试。';
  end;
end;
