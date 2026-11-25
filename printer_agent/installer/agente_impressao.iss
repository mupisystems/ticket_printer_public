; =============================================================================
;  Agente de Impressão - instalador (Inno Setup 6)
;  MupiSystems - Meu Atendimento Virtual
;
;  Normalmente compilado pelo build_installer.bat (pasta printer_agent).
;  Manualmente, na pasta printer_agent:
;    python installer\make_wizard_images.py
;    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=2.2.1 installer\agente_impressao.iss
;
;  Defines opcionais (/DNome=valor):
;    AppVersion     versão do produto (e do nome do arquivo)  padrão: 0.0.0
;    SourceDir      build ONEDIR do PyInstaller                padrão: ..\dist\AgenteImpressao
;    WebView2Setup  bootstrapper do WebView2 a embutir         padrão: installer\MicrosoftEdgeWebview2Setup.exe
;                   (embutido somente se o arquivo existir na hora da compilação)
;  Caminhos relativos são resolvidos a partir desta pasta (installer\).
; =============================================================================

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\AgenteImpressao"
#endif
#ifndef WebView2Setup
  #define WebView2Setup "MicrosoftEdgeWebview2Setup.exe"
#endif

#define AppName        "Agente de Impressão"
#define AppPublisher   "MupiSystems"
#define AppProductLine "Meu Atendimento Virtual"
; /DTestBuild=<pasta>: instalador de teste que não encosta na instalação real
; (outro AppId, outros nomes, não encerra processos e só limpa a <pasta> indicada).
#ifdef TestBuild
  #define AppExeName   "AgenteImpressaoTeste.exe"
  #define RunValueName "MeuAtendimentoPrinterAgentTeste"
  #define AppGuid      "0F5E6E0A-5B0C-4C57-9E57-7E57E57E57E5"
#else
  #define AppExeName   "AgenteImpressao.exe"
  #define RunValueName "MeuAtendimentoPrinterAgent"
  #define AppGuid      "800E2367-B407-4936-B1FD-8F057DF917E1"
#endif
; Mesma chave/valor usados pelo próprio app (windows_startup.py)
#define RunKey         "Software\Microsoft\Windows\CurrentVersion\Run"
#define WebView2Client "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

; ---- resolve caminhos relativos a partir da pasta deste script ---------------
#define AbsPath(str P) \
  (Pos(":", P) > 0 || Copy(P, 1, 2) == "\\") ? RemoveBackslashUnlessRoot(P) : AddBackslash(SourcePath) + RemoveBackslashUnlessRoot(P)

#define SrcDir AbsPath(SourceDir)
#if !FileExists(SrcDir + "\" + AppExeName)
  #pragma message "Pasta de origem: " + SrcDir
  #error Build ONEDIR não encontrado (AgenteImpressao.exe). Gere com build_exe.bat ou informe /DSourceDir=...
#endif

#if !FileExists(AddBackslash(SourcePath) + "assets\wizard-large-202x386.bmp") || !FileExists(AddBackslash(SourcePath) + "assets\wizard-small-58.bmp")
  #error Imagens do assistente não encontradas. Rode: python installer\make_wizard_images.py
#endif

#define WebView2SetupFull AbsPath(WebView2Setup)
#ifexist WebView2SetupFull
  #define BundleWebView2
  #pragma message "WebView2: bootstrapper embutido (" + WebView2SetupFull + ")"
#else
  #pragma message "WebView2: bootstrapper ausente; o instalador apenas avisará se o runtime faltar"
#endif

[Setup]
AppId={{{#AppGuid}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=© {#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalador do {#AppName} - {#AppProductLine}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}

; Instalação por usuário, sem UAC; o diálogo permite optar por "todos os usuários"
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

DefaultDirName={autopf}\{#AppProductLine}\{#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
AlwaysShowDirOnReadyPage=yes
ShowLanguageDialog=no
SetupMutex={#RunValueName}Setup,Global\{#RunValueName}Setup
; As instâncias são encerradas via taskkill em PrepareToInstall; o Restart
; Manager fica só como rede de segurança e o app não é reiniciado por ele.
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

OutputDir=..\dist\installer
OutputBaseFilename=AgenteImpressao-Setup-{#AppVersion}
SetupIconFile=..\printer_agent.ico
Compression=lzma2/max
SolidCompression=yes

WizardStyle=modern
; Gerados por make_wizard_images.py (100% a 250% de DPI)
WizardImageFile=assets\wizard-large-202x386.bmp,assets\wizard-large-269x515.bmp,assets\wizard-large-336x643.bmp,assets\wizard-large-403x772.bmp,assets\wizard-large-430x824.bmp,assets\wizard-large-498x953.bmp,assets\wizard-large-534x1022.bmp
WizardSmallImageFile=assets\wizard-small-58.bmp,assets\wizard-small-77.bmp,assets\wizard-small-97.bmp,assets\wizard-small-116.bmp,assets\wizard-small-124.bmp,assets\wizard-small-143.bmp,assets\wizard-small-159.bmp

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
WelcomeLabel1=Bem-vindo ao instalador do [name]
WelcomeLabel2=Este assistente vai instalar o [name/ver] neste computador.%n%nO Agente de Impressão recebe as senhas emitidas pelo {#AppProductLine} e as imprime automaticamente na impressora térmica do totem ou do balcão.%n%nClique em Avançar para continuar.
FinishedHeadingLabel=Tudo pronto!
FinishedLabel=O [name] foi instalado neste computador.%n%nNa primeira vez que for aberto, um assistente rápido ajuda a conectar o agente à sua conta e a escolher a impressora. Depois disso ele fica em execução na bandeja do sistema, ao lado do relógio.
FinishedLabelNoIcons=O [name] foi instalado neste computador.%n%nNa primeira vez que for aberto, um assistente rápido ajuda a conectar o agente à sua conta e a escolher a impressora. Depois disso ele fica em execução na bandeja do sistema, ao lado do relógio.
ClickFinish=Clique em Concluir para fechar o instalador.

[CustomMessages]
AutoStartTask=Iniciar junto com o Windows
LaunchNow=Abrir o Agente de Impressão agora
ShortcutComment=Recebe e imprime as senhas do {#AppProductLine}
InstallingWebView2=Instalando o Microsoft Edge WebView2 Runtime (pode levar alguns minutos)...
WebView2Missing=O {#AppName} precisa do Microsoft Edge WebView2 Runtime, que não foi encontrado neste computador.%n%nA instalação vai continuar normalmente, mas a janela do agente só vai abrir depois que o WebView2 for instalado. Ele é gratuito e pode ser baixado em:%nhttps://developer.microsoft.com/microsoft-edge/webview2/%n%nDica: no Windows 11 ele já vem instalado; manter o Windows atualizado normalmente resolve.
WebView2Failed=Não foi possível instalar o Microsoft Edge WebView2 Runtime automaticamente (verifique a conexão com a internet).%n%nO {#AppName} foi instalado, mas a janela dele só vai abrir depois que o WebView2 for instalado. Ele é gratuito e pode ser baixado em:%nhttps://developer.microsoft.com/microsoft-edge/webview2/

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:AutoStartTask}"; GroupDescription: "{cm:AutoStartProgramGroupDescription}"

[InstallDelete]
; Atualização limpa do build ONEDIR (evita bibliotecas órfãs de versões anteriores)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef BundleWebView2
Source: "{#WebView2SetupFull}"; DestName: "MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy
#endif

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Comment: "{cm:ShortcutComment}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Comment: "{cm:ShortcutComment}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "{#RunKey}"; ValueType: string; ValueName: "{#RunValueName}"; ValueData: """{app}\{#AppExeName}"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchNow}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\install.id"
; Os dados do usuário (%APPDATA%\MeuAtendimento) são preservados de propósito.

[Code]
var
  AppWasRunning: Boolean;
  RunningOld: TStringList;
  RemovedCount: Integer;

{ ---------------------------------------------------------------- processos }

{ True para o próprio instalador (Setup .exe e o assistente .tmp extraído), que
  não pode ser encerrado caso alguém o renomeie no padrão antigo "App de Impressao...". }
function IsOwnSetupImage(const ImageName: String): Boolean;
var
  SetupName: String;
begin
  Result := False;
  if IsUninstaller then
    Exit;
  SetupName := Lowercase(ExtractFileName(ExpandConstant('{srcexe}')));
  Result := (Lowercase(ImageName) = SetupName) or
            (Lowercase(ImageName) = ChangeFileExt(SetupName, '.tmp'));
end;

{ Encerra os processos cujo nome casa com Pattern ("*" só no fim, como no
  tasklist). Usa tasklist /FO CSV (independe do idioma do Windows) e taskkill /PID.
  Retorna True se algum processo foi encerrado. }
function KillProcesses(const Pattern: String): Boolean;
var
  Output: TExecOutput;
  ResultCode, I, P: Integer;
  Line, ImageName, Pid, PidArgs: String;
begin
  Result := False;
  PidArgs := '';
  try
    if not ExecAndCaptureOutput(ExpandConstant('{sys}\tasklist.exe'),
         '/FO CSV /NH /FI "IMAGENAME eq ' + Pattern + '"', '',
         SW_HIDE, ewWaitUntilTerminated, ResultCode, Output) then
      Exit;
  except
    Log('tasklist falhou: ' + GetExceptionMessage);
    Exit;
  end;

  { Linhas no formato: "Nome.exe","1234","Console","1","10.000 K" }
  for I := 0 to GetArrayLength(Output.StdOut) - 1 do
  begin
    Line := Trim(Output.StdOut[I]);
    if (Length(Line) < 2) or (Line[1] <> '"') then
      Continue;
    Delete(Line, 1, 1);
    P := Pos('","', Line);
    if P = 0 then
      Continue;
    ImageName := Copy(Line, 1, P - 1);
    Delete(Line, 1, P + 2);
    P := Pos('"', Line);
    if P = 0 then
      Continue;
    Pid := Copy(Line, 1, P - 1);
    if (StrToIntDef(Pid, 0) = 0) or IsOwnSetupImage(ImageName) then
      Continue;
    Log(Format('Encerrando %s (PID %s)', [ImageName, Pid]));
    PidArgs := PidArgs + ' /PID ' + Pid;
  end;

  if PidArgs <> '' then
  begin
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T' + PidArgs, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Result := True;
  end;
end;

{ Encerra a versão atual e os executáveis "onefile" antigos (que seguram a trava
  de instância única). Retorna True se algum processo estava em execução. }
function CloseRunningInstances: Boolean;
begin
  Result := False;
#ifndef TestBuild
  if KillProcesses('{#AppExeName}') then Result := True;
  if KillProcesses('App de Impressao*') then Result := True;        { App de Impressao - Meu Atendimento Virtual X.Y.Z.exe }
  if KillProcesses('App-de-Impressao*') then Result := True;        { App-de-Impressao.exe, App-de-Impressao-V2.exe }
  if KillProcesses('Agente-de-Impressao*') then Result := True;
  if KillProcesses('agente-impressao*') then Result := True;       { nome do download antigo no site }
  if KillProcesses('impressao-siga.exe') then Result := True;
#endif
  if Result then
    Sleep(1500); { dá tempo ao Windows de liberar os arquivos }
end;

{ ---------------------------------------------------------------- inicialização automática }

function RunValuePointsToThisApp(const Value: String): Boolean;
begin
  Result := Pos(Lowercase(ExpandConstant('{app}\{#AppExeName}')), Lowercase(Value)) > 0;
end;

{ Sem a tarefa "Iniciar junto com o Windows": remove valor Run obsoleto que
  aponte para um executável antigo (ele abriria a versão velha no logon). Um
  valor que já aponta para esta instalação foi ligado pelo próprio app e fica. }
procedure CleanupStaleRunValue;
var
  Value: String;
begin
  if RegQueryStringValue(HKCU, '{#RunKey}', '{#RunValueName}', Value) and
     not RunValuePointsToThisApp(Value) then
  begin
    Log('Removendo inicialização automática obsoleta: ' + Value);
    RegDeleteValue(HKCU, '{#RunKey}', '{#RunValueName}');
  end;
end;

{ ---------------------------------------------------------------- versões anteriores }

const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{{#AppGuid}}_is1';

{ Desinstala (em silêncio) uma instalação anterior registrada em RootKey quando
  ela está em OUTRA pasta — ex.: instalada "para todos os usuários" em Program
  Files e agora "só para mim", ou vice-versa. Na mesma pasta a atualização é
  feita no lugar. A configuração do usuário (%APPDATA%) é mantida pelo desinstalador. }
procedure UninstallOtherInstall(RootKey: Integer; const Scope: String);
var
  UninstallString, Location: String;
  ResultCode, Waited: Integer;
begin
  if not RegQueryStringValue(RootKey, UninstallKey, 'UninstallString', UninstallString) then
    Exit;
  RegQueryStringValue(RootKey, UninstallKey, 'InstallLocation', Location);
  if CompareText(RemoveBackslashUnlessRoot(Location), RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) = 0 then
  begin
    Log('Versão anterior na mesma pasta (' + Scope + '): será substituída no lugar.');
    Exit;
  end;
  UninstallString := RemoveQuotes(UninstallString);
  if not FileExists(UninstallString) then
  begin
    Log('Registro de versão anterior sem desinstalador (' + Scope + '): ' + UninstallString);
    Exit;
  end;
  Log('Desinstalando versão anterior em outra pasta (' + Scope + '): ' + Location);
  { ShellExec: se a versão antiga foi instalada para todos os usuários, o Windows pede permissão de administrador }
  if not ShellExec('', UninstallString, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE,
                   ewWaitUntilTerminated, ResultCode) then
  begin
    Log('Não foi possível executar o desinstalador anterior: ' + SysErrorMessage(ResultCode));
    Exit;
  end;
  { O desinstalador do Inno se copia para a pasta temporária e continua lá:
    espera o registro sumir (até 60 s). }
  Waited := 0;
  while RegValueExists(RootKey, UninstallKey, 'UninstallString') and (Waited < 60000) do
  begin
    Sleep(500);
    Waited := Waited + 500;
  end;
  if RegValueExists(RootKey, UninstallKey, 'UninstallString') then
    Log('A versão anterior ainda consta como instalada após 60 s.')
  else
    Log('Versão anterior removida.');
end;

procedure UninstallOtherInstalls;
begin
  if IsWin64 then
    UninstallOtherInstall(HKLM64, 'todos os usuários');
  UninstallOtherInstall(HKLM32, 'todos os usuários (32 bits)');
  UninstallOtherInstall(HKCU, 'usuário atual');
end;

{ Nomes das versões antigas (executável único). O instalador novo chama-se
  AgenteImpressao-Setup, que não casa com nenhum destes. }
function IsOldExeName(const FileName: String): Boolean;
var
  N: String;
begin
  N := Lowercase(ExtractFileName(FileName));
  Result := (ExtractFileExt(N) = '.exe') and
    ((Pos('app de impressao', N) = 1) or (Pos('app-de-impressao', N) = 1) or
     (Pos('app.de.impressao', N) = 1) or (Pos('agente-de-impressao', N) = 1) or
     (Pos('agente-impressao', N) = 1) or (N = 'impressao-siga.exe') or (N = 'printer_agent.exe'));
end;

function IsOldFolderName(const FolderName: String): Boolean;
var
  N: String;
begin
  N := Lowercase(FolderName);
  Result := (Pos('app de impressao', N) = 1) or (Pos('app-de-impressao', N) = 1) or
            (Pos('app.de.impressao', N) = 1) or (Pos('agente-impressao', N) = 1);
end;

{ Nunca toca na instalação nova nem no próprio instalador. }
function MayRemove(const Path: String): Boolean;
begin
  Result := IsOldExeName(Path) and
    (Pos(Lowercase(AddBackslash(ExpandConstant('{app}'))), Lowercase(Path)) <> 1) and
    (CompareText(Path, ExpandConstant('{srcexe}')) <> 0);
end;

procedure RemoveOldFile(const Path, What: String);
var
  I: Integer;
begin
  if not FileExists(Path) then
    Exit;
  for I := 1 to 6 do
  begin
    if DeleteFile(Path) then
    begin
      Log('[limpeza] removido ' + What + ': ' + Path);
      RemovedCount := RemovedCount + 1;
      Exit;
    end;
    Sleep(400);   { o Windows pode demorar a soltar o arquivo após encerrar o processo }
  end;
  Log('[limpeza] NÃO foi possível remover ' + What + ': ' + Path);
end;

{ Executáveis antigos numa pasta e nas subpastas com nome da versão antiga (zip extraído). }
procedure RemoveOldExesIn(const Folder: String; const Depth: Integer);
var
  Rec: TFindRec;
  Found, Sub: TStringList;
  I: Integer;
begin
  if (Folder = '') or not DirExists(Folder) then
    Exit;
  Log('[limpeza] verificando: ' + Folder);
  Found := TStringList.Create;
  Sub := TStringList.Create;
  try
    if FindFirst(AddBackslash(Folder) + '*', Rec) then
    try
      repeat
        if (Rec.Attributes and FILE_ATTRIBUTE_DIRECTORY) = 0 then
        begin
          if MayRemove(AddBackslash(Folder) + Rec.Name) then
            Found.Add(AddBackslash(Folder) + Rec.Name);
        end
        else if (Depth > 0) and IsOldFolderName(Rec.Name) then
          Sub.Add(AddBackslash(Folder) + Rec.Name);
      until not FindNext(Rec);
    finally
      FindClose(Rec);
    end;
    for I := 0 to Found.Count - 1 do
      RemoveOldFile(Found[I], 'executável antigo');
    for I := 0 to Sub.Count - 1 do
      RemoveOldExesIn(Sub[I], Depth - 1);
  finally
    Found.Free;
    Sub.Free;
  end;
end;

{ Atalhos (.lnk) que apontam para versões antigas. }
procedure RemoveOldShortcutsIn(const Folder: String; const Depth: Integer);
var
  Rec: TFindRec;
  Found, Sub: TStringList;
  Shell, Link: Variant;
  Target: String;
  I: Integer;
begin
  if (Folder = '') or not DirExists(Folder) then
    Exit;
  Found := TStringList.Create;
  Sub := TStringList.Create;
  try
    if FindFirst(AddBackslash(Folder) + '*', Rec) then
    try
      repeat
        if (Rec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
        begin
          if (Depth > 0) and (Rec.Name <> '.') and (Rec.Name <> '..') then
            Sub.Add(AddBackslash(Folder) + Rec.Name);
        end
        else if CompareText(ExtractFileExt(Rec.Name), '.lnk') = 0 then
          Found.Add(AddBackslash(Folder) + Rec.Name);
      until not FindNext(Rec);
    finally
      FindClose(Rec);
    end;
    if Found.Count > 0 then
    begin
      Shell := CreateOleObject('WScript.Shell');
      for I := 0 to Found.Count - 1 do
      begin
        Target := '';
        try
          Link := Shell.CreateShortcut(Found[I]);
          Target := Link.TargetPath;
        except
          Log('[limpeza] atalho ilegível: ' + Found[I]);
        end;
        if (Target <> '') and MayRemove(Target) then
          RemoveOldFile(Found[I], 'atalho antigo (para ' + Target + ')');
      end;
    end;
    for I := 0 to Sub.Count - 1 do
      RemoveOldShortcutsIn(Sub[I], Depth - 1);
  finally
    Found.Free;
    Sub.Free;
  end;
end;

function ExeFromCommand(const Command: String): String;
var
  P: Integer;
begin
  Result := Trim(Command);
  if (Result <> '') and (Result[1] = '"') then
    Delete(Result, 1, 1);
  P := Pos('.exe', Lowercase(Result));
  if P > 0 then
    Result := Copy(Result, 1, P + 3)
  else
    Result := '';
end;

{ Anota de onde as versões antigas estão rodando ANTES de encerrá-las: pega
  também as que ficam fora das pastas conhecidas. }
procedure CollectRunningOldExes;
var
  Locator, Service, Items, Item: Variant;
  Path: String;
  I: Integer;
begin
  RunningOld := TStringList.Create;
#ifndef TestBuild
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2');
    Items := Service.ExecQuery('SELECT ExecutablePath FROM Win32_Process WHERE ExecutablePath IS NOT NULL');
    for I := 0 to Items.Count - 1 do
    begin
      Item := Items.ItemIndex(I);
      Path := Item.ExecutablePath;
      if MayRemove(Path) and (RunningOld.IndexOf(Path) < 0) then
        RunningOld.Add(Path);
    end;
  except
    Log('[limpeza] não foi possível listar os processos: ' + GetExceptionMessage);
  end;
#endif
end;

procedure CleanupOldVersions;
var
  Value, Downloads: String;
  I: Integer;
begin
  RemovedCount := 0;
  try
    for I := 0 to RunningOld.Count - 1 do
      RemoveOldFile(RunningOld[I], 'executável antigo que estava rodando');
    if RegQueryStringValue(HKCU, '{#RunKey}', '{#RunValueName}', Value) then
    begin
      Value := ExeFromCommand(Value);
      if (Value <> '') and MayRemove(Value) then
        RemoveOldFile(Value, 'executável antigo da inicialização automática');
    end;
#ifdef TestBuild
    RemoveOldShortcutsIn('{#TestBuild}', 1);
    RemoveOldExesIn('{#TestBuild}', 1);
#else
    Downloads := '';
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders',
                           '{374DE290-123F-4565-9164-39C4925E467B}', Value) then
      Downloads := Value;
    { atalhos primeiro: o destino ainda é comparado pelo nome }
    RemoveOldShortcutsIn(ExpandConstant('{userdesktop}'), 0);
    RemoveOldShortcutsIn(ExpandConstant('{commondesktop}'), 0);
    RemoveOldShortcutsIn(ExpandConstant('{userprograms}'), 1);
    RemoveOldShortcutsIn(ExpandConstant('{commonprograms}'), 1);
    RemoveOldShortcutsIn(ExpandConstant('{userstartup}'), 0);
    RemoveOldShortcutsIn(ExpandConstant('{commonstartup}'), 0);
    RemoveOldExesIn(ExpandConstant('{userdesktop}'), 1);
    RemoveOldExesIn(ExpandConstant('{commondesktop}'), 1);
    RemoveOldExesIn(Downloads, 1);
    RemoveOldExesIn('C:\MeuAtendimento', 1);
#endif
    Log('[limpeza] concluída: ' + IntToStr(RemovedCount) + ' item(ns) de versões antigas removido(s).');
  except
    Log('[limpeza] ERRO: ' + GetExceptionMessage);
  end;
end;

{ Marca esta instalação: o app mostra o fluxo de boas-vindas do início (mantendo
  a configuração) até ele ser concluído para este identificador. }
procedure WriteInstallId;
begin
  SaveStringToFile(ExpandConstant('{app}\install.id'),
    '{#AppVersion}-' + GetDateTimeString('yyyymmddhhnnss', #0, #0), False);
end;

{ ---------------------------------------------------------------- WebView2 }

function IsValidWebView2Version(const Version: String): Boolean;
begin
  Result := (Trim(Version) <> '') and (Trim(Version) <> '0.0.0.0');
end;

function WebView2Installed: Boolean;
var
  Version: String;
begin
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{#WebView2Client}', 'pv', Version) and IsValidWebView2Version(Version)) or
    (RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{#WebView2Client}', 'pv', Version) and IsValidWebView2Version(Version)) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{#WebView2Client}', 'pv', Version) and IsValidWebView2Version(Version));
  if Result then
    Log('WebView2 Runtime encontrado: ' + Version)
  else
    Log('WebView2 Runtime não encontrado.');
end;

#ifdef BundleWebView2
procedure InstallWebView2;
var
  ResultCode: Integer;
begin
  WizardForm.StatusLabel.Caption := CustomMessage('InstallingWebView2');
  WizardForm.FilenameLabel.Caption := '';
  WizardForm.ProgressGauge.Style := npbstMarquee;
  try
    ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
    if Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '',
            SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Log('Bootstrapper do WebView2 terminou com código ' + IntToStr(ResultCode))
    else
      Log('Falha ao executar o bootstrapper do WebView2: ' + SysErrorMessage(ResultCode));
  finally
    WizardForm.ProgressGauge.Style := npbstNormal;
  end;

  if not WebView2Installed then
    SuppressibleMsgBox(CustomMessage('WebView2Failed'), mbInformation, MB_OK, IDOK);
end;
#endif

{ ---------------------------------------------------------------- eventos do Setup }

function InitializeSetup: Boolean;
begin
  Result := True;
#ifndef BundleWebView2
  if not WebView2Installed and not WizardSilent then
    SuppressibleMsgBox(CustomMessage('WebView2Missing'), mbInformation, MB_OK, IDOK);
#endif
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  { 1. fecha o que estiver rodando; 2. remove instalações em outras pastas;
    3. apaga executáveis avulsos e atalhos antigos. A configuração é mantida. }
  CollectRunningOldExes;
  AppWasRunning := CloseRunningInstances;
  UninstallOtherInstalls;
  CleanupOldVersions;
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    WriteInstallId;
    if not WizardIsTaskSelected('autostart') then
      CleanupStaleRunValue;
#ifdef BundleWebView2
    if not WebView2Installed then
      InstallWebView2;
#endif
  end
  else if (CurStep = ssDone) and WizardSilent and AppWasRunning then
  begin
    { Atualização silenciosa: o agente estava rodando, então volta para a bandeja }
    ExecAsOriginalUser(ExpandConstant('{app}\{#AppExeName}'), '--background', ExpandConstant('{app}'),
                       SW_SHOWNORMAL, ewNoWait, ResultCode);
  end;
end;

{ ---------------------------------------------------------------- eventos do desinstalador }

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Value: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    CloseRunningInstances;
    { Remove também o valor Run criado pelo próprio app (fora da tarefa do instalador) }
    if RegQueryStringValue(HKCU, '{#RunKey}', '{#RunValueName}', Value) and RunValuePointsToThisApp(Value) then
      RegDeleteValue(HKCU, '{#RunKey}', '{#RunValueName}');
  end;
end;
