; 定时清理指定文件夹 — Inno Setup 安装脚本
; 功能：
;   1. 安装向导左侧自定义图片
;   2. 检测指定路径是否已安装（注册表）
;   3. 旧版本检测 → 提示先卸载后安装（可选，默认勾选保留用户数据）
;   4. 一键卸载（Inno Setup 自带 unins000.exe + 开始菜单快捷方式）

#define MyAppName "定时清理指定文件夹"
#define MyAppExeName "FolderCleaner.exe"
#define MyAppVersion "1.22"
#define MyAppPublisher "Local"
#define MyAppId "{{8F3C2E4A-9B1D-4C5E-A7F0-2D6B8E1C4A35}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FolderCleaner
DefaultGroupName={#MyAppName}
; 左侧图片（328x628 高清，modern 风格显示在向导左侧）
WizardStyle=modern
WizardImageFile=resources\install_side.png
; 卸载信息
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
; 兼容性
MinVersion=10.0.17763
PrivilegesRequired=lowest
OutputDir=dist\installer
OutputBaseFilename=FolderCleaner_Setup
SetupIconFile=resources\icons\app.ico
Compression=lzma2
SolidCompression=yes
; 卸载确认时显示保留数据的说明
UninstallDisplaySize=54000000

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: unchecked
Name: "autostart"; Description: "开机自动启动（常驻后台）"; GroupDescription: "启动选项："

[Files]
; 主程序（单文件 exe）
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; 卸载说明文档
Source: "安装说明.txt"; DestDir: "{app}"; Flags: ignoreversion; AfterInstall: AddUninstallNote

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; 记录安装信息供版本检测
Root: HKCU; Subkey: "Software\FolderCleaner"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\FolderCleaner"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletevalue

[Run]
; 安装完成后自动启动（可选）
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时删除安装目录内的回收站文件夹（若位于安装目录）
Type: filesandordirs; Name: "{app}\recycle_bin"

[Code]
// ---------- 版本比较 ----------
function CompareVersions(v1, v2: string): Integer;
var
  p1, p2, n1, n2, c1, c2: Integer;
  s1, s2: string;
begin
  Result := 0;
  s1 := v1; s2 := v2;
  while (s1 <> '') or (s2 <> '') do
  begin
    p1 := Pos('.', s1); p2 := Pos('.', s2);
    if p1 = 0 then p1 := Length(s1) + 1;
    if p2 = 0 then p2 := Length(s2) + 1;
    if p1 = 1 then n1 := 0 else n1 := StrToIntDef(Copy(s1, 1, p1 - 1), 0);
    if p2 = 1 then n2 := 0 else n2 := StrToIntDef(Copy(s2, 1, p2 - 1), 0);
    if n1 > n2 then begin Result := 1; Exit; end;
    if n1 < n2 then begin Result := -1; Exit; end;
    s1 := Copy(s1, p1 + 1, Length(s1));
    s2 := Copy(s2, p2 + 1, Length(s2));
  end;
end;

// ---------- 读取已安装版本（注册表） ----------
function GetInstalledVersion(): string;
var
  ver: string;
begin
  Result := '';
  // Inno Setup 卸载注册表
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + '{#MyAppId}' + '_is1', 'DisplayVersion', ver) then
    Result := ver
  else if RegQueryStringValue(HKCU, 'Software\FolderCleaner', 'Version', ver) then
    Result := ver;
end;

// ---------- 读取已安装路径 ----------
function GetInstalledPath(): string;
var
  path: string;
begin
  Result := '';
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + '{#MyAppId}' + '_is1', 'InstallLocation', path) then
    Result := path
  else if RegQueryStringValue(HKCU, 'Software\FolderCleaner', 'InstallPath', path) then
    Result := path;
end;

// ---------- 读取旧卸载程序路径 ----------
function GetOldUninstallString(): string;
var
  s: string;
begin
  Result := '';
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + '{#MyAppId}' + '_is1', 'UninstallString', s) then
    Result := s;
end;

// ---------- 卸载旧版本（静默，保留用户数据） ----------
function UninstallOldVersion(keepData: Boolean): Boolean;
var
  uninst: string;
  params: string;
  ResultCode: Integer;
begin
  Result := True;
  uninst := GetOldUninstallString();
  if uninst = '' then Exit;
  // 去除引号
  uninst := RemoveQuotes(uninst);
  if FileExists(uninst) then
  begin
    params := '/VERYSILENT /NORESTART';
    // 不保留数据时传自定义参数，卸载脚本据此前置删除用户数据
    if not keepData then
      params := params + ' /DELETEUSERDATA';
    if Exec(uninst, params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Result := (ResultCode = 0) or (ResultCode = 1)  // 0=正常卸载, 1=用户取消也放行
    else
      Result := False;
  end;
end;

// ---------- 升级检测页（先卸载后安装 + 保留数据选项） ----------
// 手动创建两个独立 TNewCheckBox，绝对互不干扰（多选）
var
  UpgradePage: TWizardPage;
  ChkUninstall: TNewCheckBox;
  ChkKeepData: TNewCheckBox;
  InfoLabel: TNewStaticText;
  UpgradeDetected: Boolean;

procedure InitializeWizard;
begin
  UpgradeDetected := False;
  // 创建自定义页面
  UpgradePage := CreateCustomPage(
    wpWelcome, '检测到旧版本', '建议先卸载旧版本再安装新版本');

  // 版本信息标签（检测到旧版本时填充）
  InfoLabel := TNewStaticText.Create(UpgradePage);
  InfoLabel.Parent := UpgradePage.Surface;
  InfoLabel.Left := 24;
  InfoLabel.Top := 8;
  InfoLabel.Width := UpgradePage.SurfaceWidth - 48;
  InfoLabel.AutoSize := False;
  InfoLabel.WordWrap := True;
  InfoLabel.Caption := '正在检测已安装版本...';

  // 复选框 1：先卸载旧版本（默认勾选）
  ChkUninstall := TNewCheckBox.Create(UpgradePage);
  ChkUninstall.Parent := UpgradePage.Surface;
  ChkUninstall.Caption := '先卸载旧版本，再安装新版本（推荐）';
  ChkUninstall.Left := 24;
  ChkUninstall.Top := 76;
  ChkUninstall.Width := UpgradePage.SurfaceWidth - 48;
  ChkUninstall.Checked := True;

  // 复选框 2：保留用户数据（默认勾选）— 与选项 1 完全独立
  ChkKeepData := TNewCheckBox.Create(UpgradePage);
  ChkKeepData.Parent := UpgradePage.Surface;
  ChkKeepData.Caption := '保留用户数据（设置、日志、回收站内容）';
  ChkKeepData.Left := 24;
  ChkKeepData.Top := 112;
  ChkKeepData.Width := UpgradePage.SurfaceWidth - 48;
  ChkKeepData.Checked := True;
end;

function ShouldShowUpgradePage(): Boolean;
begin
  Result := UpgradeDetected;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  oldVer, newVer: string;
begin
  Result := True;

  // 在欢迎页之后显示升级检测逻辑
  if CurPageID = wpWelcome then
  begin
    oldVer := GetInstalledVersion();
    newVer := '{#MyAppVersion}';
    if (oldVer <> '') and (CompareVersions(oldVer, newVer) < 0) then
    begin
      UpgradeDetected := True;
      // 更新页面文本
      InfoLabel.Caption :=
        '检测到已安装版本 ' + oldVer + '，当前安装版本 ' + newVer + '。' + #13#10 +
        '建议先卸载旧版本再安装新版本。' + #13#10 + #13#10 +
        '已安装位置：' + GetInstalledPath();
      Result := True;
    end
    else
      UpgradeDetected := False;
  end;

  // 升级页点击"下一步"：执行卸载
  if CurPageID = UpgradePage.ID then
  begin
    if ChkUninstall.Checked then
    begin
      if not UninstallOldVersion(ChkKeepData.Checked) then
      begin
        if MsgBox('卸载旧版本失败或已取消。是否继续安装？', mbConfirmation, MB_YESNO) = IDNO then
          Result := False;
      end;
    end;
  end;
end;

// 安装说明文件生成
procedure AddUninstallNote;
var
  note: string;
begin
  // 占位（实际由 安装说明.txt 静态文件提供）
end;

// ---------- 卸载时处理用户数据 ----------
// 默认保留用户数据（%APPDATA%\CleanFolderApp）
// 仅当卸载程序收到 /DELETEUSERDATA 参数时才删除用户数据

function CmdLineHas(Param: string): Boolean;
var
  i: Integer;
begin
  Result := False;
  for i := 1 to ParamCount do
    if CompareText(ParamStr(i), '/' + Param) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  dataDir: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    if CmdLineHas('DELETEUSERDATA') then
    begin
      dataDir := ExpandConstant('{userappdata}\CleanFolderApp');
      if DirExists(dataDir) then
        DelTree(dataDir, True, True, True);
    end;
  end;
end;
