; Inno Setup 安装包脚本：思小诘 · 苏格拉底学习助手
; 编译前先执行 PyInstaller 构建（dist\SiXiaoJie\ 为打包产物）
; 编译：ISCC.exe installer.iss

#define MyAppName "思小诘学习助手"
#define MyAppNameEn "SiXiaoJie"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "思小诘 SiXiaoJie"
#define MyAppExeName "SiXiaoJie.exe"
#define MyAppDescription "苏格拉底式 AI 学习伙伴"

[Setup]
AppId={{B6F4A9C2-8E3D-4F7A-9B5E-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; 按用户安装，无需管理员权限
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=SiXiaoJie-Setup-{#MyAppVersion}
SetupIconFile=
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
ChangesAssociations=no
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "chs"; MessagesFile: "ChineseSimplified.isl"

[CustomMessages]
; 中文补充文案（首启说明等）
CreateDesktopIcon=创建桌面快捷方式
LaunchProgram=立即运行 {#MyAppName}
AdditionalTasks=附加任务:

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalTasks}"; Flags: checkedonce

[Files]
Source: "dist\SiXiaoJie\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时清理空的安装目录（用户数据在 %APPDATA%\SiXiaoJie，不随卸载删除）
Type: filesandordirs; Name: "{app}"
