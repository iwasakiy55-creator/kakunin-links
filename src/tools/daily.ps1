# 毎日の見回り：リポジトリを最新にする → リンクを確かめる → 画面を作り直す → GitHub Pages へ上げる。
# タスク スケジューラー「リンク集の見回り（毎日19時）」から動く。手で動かすときは -Manual
param([switch]$Manual)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Split-Path -Parent $here
$repo = Split-Path -Parent $src
$log = Join-Path $here 'daily.log'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
function L($t) { $line = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + '  ' + $t; Add-Content -Path $log -Value $line -Encoding UTF8; Write-Host $line }
try {
  Push-Location $repo
  L '見回りを始めます'
  git pull -q --rebase --autostash 2>&1 | Out-Null
  & (Join-Path $here 'check.ps1') -Quiet | Out-Host
  & py -X utf8 (Join-Path $src 'build.py') | Out-Host
  if ($LASTEXITCODE -ne 0) { throw '画面を作れませんでした' }
  git add -A | Out-Null
  git diff --cached --quiet
  if ($LASTEXITCODE -ne 0) {
    git commit -q -m ("見回り " + (Get-Date).ToString('yyyy-MM-dd HH:mm')) | Out-Null
    git push -q 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw '公開の置き場へ上げられませんでした' }
    L '公開の置き場へ上げました'
  } else { L '変わったところはありませんでした' }
  L '終わりました'
} catch { L ('止まりました：' + $_) } finally { Pop-Location }
if ($Manual) { Read-Host '  Enter キーで閉じます' }
