'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { classifyPowerShell } = require('../src/agent/powershellPolicy');

const READ_ONLY = [
  'Get-Process',
  'Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name, Id, WorkingSet64',
  "Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory, TotalVisibleMemorySize",
  "Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | Select-Object DeviceID, @{n='WolneGB';e={[math]::Round($_.FreeSpace/1GB,1)}}",
  'Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum',
  "Get-WinEvent -LogName System -MaxEvents 20 | Where-Object { $_.LevelDisplayName -eq 'Błąd' } | Format-List",
  'Get-Service | ? Status -eq Running | ft -AutoSize',
  'ipconfig /all',
  'ipconfig',
  'netstat -ano | Select-String 443',
  'Get-ChildItem C:\\Users\\Jan\\Documents -Filter *.pdf | % { $_.Name.ToUpper() }',
  '$p = Get-Process; $p.Count',
  'Test-Path "C:\\Windows\\Temp"',
  'Get-Date -Format yyyy-MM-dd',
  "[Environment]::GetFolderPath('Desktop')",
  'Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName',
  'Get-Process 2>&1 | Out-String',
  'Get-ChildItem C:\\x 2>$null',
  'if (-not (Test-Path C:\\x)) { Write-Output "brak" }',
  'foreach ($d in Get-PSDrive -PSProvider FileSystem) { $d.Name }',
  'Get-Content C:\\Users\\Jan\\log.txt -Tail 50 # ostatnie wiersze',
  'powercfg /getactivescheme',
];

const NEEDS_CONFIRMATION = [
  ['Remove-Item C:\\Users\\Jan\\AppData\\Local\\Temp\\* -Recurse -Force', /Remove-Item/],
  ['Get-ChildItem $env:TEMP | Remove-Item -Recurse', /Remove-Item/],
  ['Stop-Process -Name chrome', /Stop-Process/],
  ['Get-Process notepad | Stop-Process', /Stop-Process/],
  ['(Get-Process notepad).Kill()', /Kill/],
  ['Get-Process | % { $_.Kill() }', /Kill/],
  ['Get-Process notepad | % Kill', /ForEach-Object/],
  ['Get-Process notepad | ForEach-Object -MemberName Kill', /ForEach-Object/],
  ['Get-Process > C:\\procesy.txt', /Przekierowanie/],
  ['Get-Process | Out-File C:\\x.txt', /Out-File/],
  ['& "C:\\Windows\\notepad.exe"', /Operator wywołania/],
  ['iex "Remove-Item C:\\x"', /iex/],
  ['Invoke-Expression $cmd', /Invoke-Expression/],
  ['Write-Output "$(Remove-Item C:\\x)"', /Podwyrażenie/],
  ['R`emove-Item C:\\x', /Znak `/],
  ['[System.IO.File]::Delete("C:\\x.txt")', /\.NET/],
  ["[Environment]::SetEnvironmentVariable('A','B','User')", /\.NET/],
  ['$f = Get-Item C:\\x.txt; $f.Attributes = "Hidden"', /Przypisanie/],
  ['. .\\skrypt.ps1', /kropką/],
  ['.\\skrypt.ps1', /nie jest na liście/],
  ['notepad.exe', /nie jest na liście/],
  ['cmd /c del C:\\x', /nie jest na liście/],
  ['ipconfig /flushdns', /ipconfig/],
  ['hostname NOWA-NAZWA', /hostname/],
  ['Get-Content $env:USERPROFILE\\.ssh\\id_rsa', /poufnych/],
  ['Get-ChildItem | Select-Object Name; Clear-RecycleBin -Force', /Clear-RecycleBin/],
  ['function X { Get-Process }; X', /Definicja/],
  ['Get-Help Remove-Item', /Remove-Item/],
  ["$s = @'\nRemove-Item x\n'@", /here-string/],
  ['{ Remove-Item C:\\x }.Invoke()', /Remove-Item/],
  ['Start-Process powershell -Verb RunAs', /Start-Process/],
  ['Get-Clipboard', /poufnych|nie jest na liście/],
  ['Set-ExecutionPolicy Bypass', /Set-ExecutionPolicy/],
  ['Get-Process | Export-Csv C:\\p.csv', /Export-Csv/],
  ['$files.ForEach("Delete")', /ForEach/],
  ['', /Puste/],
];

for (const command of READ_ONLY) {
  test(`tylko odczyt: ${command}`, () => {
    const result = classifyPowerShell(command);
    assert.equal(result.readOnly, true, `Powody: ${result.reasons.join(' | ')}`);
    assert.deepEqual(result.reasons, []);
  });
}

for (const [command, reason] of NEEDS_CONFIRMATION) {
  test(`wymaga zgody: ${command.replace(/\n/g, ' ')}`, () => {
    const result = classifyPowerShell(command);
    assert.equal(result.readOnly, false);
    assert.ok(
      result.reasons.some((item) => reason.test(item)),
      `Oczekiwano powodu ${reason}, otrzymano: ${result.reasons.join(' | ')}`,
    );
  });
}

test('ostrzeżenia o operacjach nieodwracalnych', () => {
  assert.match(classifyPowerShell('Remove-Item C:\\Dane -Recurse -Force').warnings.join(' '), /Rekurencyjne/);
  assert.match(classifyPowerShell('Format-Volume -DriveLetter D').warnings.join(' '), /dyskach/);
  assert.match(classifyPowerShell('Set-MpPreference -DisableRealtimeMonitoring $true').warnings.join(' '), /zabezpieczeń/);
  assert.deepEqual(classifyPowerShell('Get-Process').warnings, []);
});

test('lista rozpoznanych poleceń', () => {
  const result = classifyPowerShell('gps | sort CPU | select -First 3');
  assert.deepEqual(result.commands, ['get-process', 'sort-object', 'select-object']);
});
