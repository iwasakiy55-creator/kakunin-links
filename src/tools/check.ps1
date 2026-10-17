# リンクの見回り：リンク集のすべてのリンクを開いて、開けるか・ページが変わっていないかを確かめる。
# 「リンクを見回る.bat」から動く。送るのは、公開されているページの場所だけ。
param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$links = Get-Content (Join-Path $here 'links.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$urls = @($links | ForEach-Object { $_.url } | Sort-Object -Unique)
$prevPath = Join-Path $here 'status.json'
$prev = @{}
if (Test-Path $prevPath) {
  $p = Get-Content $prevPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($p.links) { $p.links.PSObject.Properties | ForEach-Object { $prev[$_.Name] = $_.Value } }
}

Write-Host ''
Write-Host '  リンクの見回りを始めます（' $urls.Count '件。数分かかります）'
Write-Host ''

$sb = {
  param($u)
  function One($u) {
    $r = @{ code = ''; final = ''; title = ''; hash = '' }
    try {
      $req = [Net.HttpWebRequest]::Create($u)
      $req.UserAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
      $req.Headers.Add('Accept-Language', 'ja')
      $req.Timeout = 25000; $req.ReadWriteTimeout = 25000; $req.AllowAutoRedirect = $true
      $res = $req.GetResponse()
      $r.code = [string][int]$res.StatusCode
      $r.final = $res.ResponseUri.AbsoluteUri
      $ct = [string]$res.ContentType
      $s = $res.GetResponseStream(); $ms = New-Object IO.MemoryStream
      $buf = New-Object byte[] 65536; $tot = 0
      while ($tot -lt 8000000) { $n = $s.Read($buf, 0, $buf.Length); if ($n -le 0) { break }; $ms.Write($buf, 0, $n); $tot += $n }
      $res.Close()
      if ($ct -match 'html') {
        $bytes = $ms.ToArray(); $enc = ''
        if ($ct -match 'charset=([\w-]+)') { $enc = $matches[1] }
        else { $head = [Text.Encoding]::ASCII.GetString($bytes, 0, [Math]::Min(4000, $bytes.Length)); if ($head -match 'charset=["'']?([\w-]+)') { $enc = $matches[1] } }
        try { $e = [Text.Encoding]::GetEncoding($enc) } catch { $e = [Text.Encoding]::UTF8 }
        $txt = $e.GetString($bytes)
        if ($txt -match '(?is)<title[^>]*>(.*?)</title>') { $r.title = ($matches[1] -replace '\s+', ' ').Trim() }
        # 中身の指紋：本文の文字だけで取る（スクリプト・飾り・タグは除く。<main> があれば、その中だけ）
        $body = $txt
        if ($body -match '(?is)<main[^>]*>(.*?)</main>') { $body = $matches[1] }
        $body = $body -replace '(?is)<script.*?</script>', ' ' -replace '(?is)<style.*?</style>', ' ' -replace '(?is)<noscript.*?</noscript>', ' ' -replace '(?s)<!--.*?-->', ' '
        $body = $body -replace '(?s)<[^>]+>', ' ' -replace '&nbsp;|&#160;', ' ' -replace '\s+', ' '
        $body = $body -replace '(閲覧数|アクセス数|カウンタ)[^ ]*', ''
        $r.hash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($body.Trim()))).Replace('-', '').Substring(0, 16)
      } else {
        # PDF などは、ファイルそのものの指紋
        $r.hash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($ms.ToArray())).Replace('-', '').Substring(0, 16)
      }
    } catch [Net.WebException] {
      if ($_.Exception.Response) { $r.code = [string][int]$_.Exception.Response.StatusCode } else { $r.code = [string]$_.Exception.Status }
    } catch { $r.code = 'Error' }
    return $r
  }
  $a = One $u
  if ($a.code -notmatch '^[23]') { Start-Sleep -Seconds 5; $a = One $u }   # 一時的に開けないことがあるので、1回だけ開き直す
  [pscustomobject]@{ url = $u; code = $a.code; final = $a.final; title = $a.title; hash = $a.hash }
}

$pool = [RunspaceFactory]::CreateRunspacePool(1, 6); $pool.Open()
$jobs = foreach ($u in $urls) { $ps = [PowerShell]::Create(); $ps.RunspacePool = $pool; [void]$ps.AddScript($sb).AddArgument($u); [pscustomobject]@{ ps = $ps; h = $ps.BeginInvoke() } }
$res = @(); $i = 0
foreach ($j in $jobs) {
  $res += $j.ps.EndInvoke($j.h); $j.ps.Dispose(); $i++
  Write-Progress -Activity 'リンクを見回っています' -Status "$i / $($urls.Count)" -PercentComplete ($i * 100 / $urls.Count)
}
$pool.Close()
Write-Progress -Activity 'リンクを見回っています' -Completed

$today = (Get-Date).ToString('yyyy-MM-dd')
$out = [ordered]@{}
$bad = 0; $moved = 0; $changed = 0
foreach ($r in $res) {
  $pv = $prev[$r.url]
  $notfound = $r.title -match '見つかりません|存在しません|Not Found|404'
  $orig = [Uri]$r.url
  $toTop = $false
  if ($r.final) { $f = [Uri]$r.final; $toTop = ($f.AbsolutePath -match '^/(index\.html?)?$') -and ($orig.AbsolutePath -notmatch '^/(index\.html?)?$') }
  $ok = ($r.code -match '^[23]') -and -not $notfound -and -not $toTop
  $fails = 0
  if (-not $ok) { $fails = 1; if ($pv -and $pv.fails) { $fails = [int]$pv.fails + 1 } }
  $chg = ''
  if ($pv -and $pv.changed) { $chg = $pv.changed }
  $why = ''; if ($pv -and $pv.why) { $why = $pv.why }
  # 例規集の検索の画面は、開くたびに中の文字が変わるので、変わったかは見ない（2026-10-18）
  $dyn = $r.url -match 'd1-law\.com/opensearch|legal-square\.com'
  if ($dyn) { $chg = ''; $why = '' }
  if (-not $dyn -and $ok -and $pv -and $pv.title -and $r.title -and ($pv.title -ne $r.title)) { $chg = $today; $why = 'title'; $changed++ }
  elseif (-not $dyn -and $ok -and $pv -and $pv.hash -and $r.hash -and ($pv.hash -ne $r.hash)) { $chg = $today; $why = 'body'; $changed++ }
  $hash = $r.hash; if (-not $ok -and $pv -and $pv.hash) { $hash = $pv.hash }
  $title = $r.title; if (-not $ok -and $pv -and $pv.title) { $title = $pv.title }
  if (-not $ok) { $bad++ }
  $kind = ''
  if ($notfound) { $kind = 'notfound' } elseif ($toTop) { $kind = 'top' }
  $out[$r.url] = [ordered]@{ code = $r.code; at = $today; fails = $fails; kind = $kind; title = $title; changed = $chg; why = $why; hash = $hash }
}
$doc = [ordered]@{ checked_at = $today; links = $out }
$json = $doc | ConvertTo-Json -Depth 4
$utf8 = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($prevPath, $json, $utf8)
[IO.File]::WriteAllText((Join-Path $here 'status.js'), "window.LINK_STATUS = $json;", $utf8)

Write-Host ''
Write-Host "  終わりました。見たリンク $($urls.Count) 件"
Write-Host "    開けない・移ったかもしれない： $bad 件（2回続けて開けないものに、印が付きます）"
Write-Host "    中身・題名が変わった　　　　： $changed 件"
Write-Host ''

