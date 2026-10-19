# 利用の回数：Cloudflare Web Analytics から、日ごとの回数を取ってきて「利用の回数.txt」に1日1行で書き足す。
# 毎日の見回り（daily.ps1）から動く。token はこの PC の環境変数 CF_API_TOKEN（読むだけ）。開発版の分は数えない。
$acct = '3a73aa41456bc6f37bbb309df49b5312'
$out  = 'G:\マイドライブ\まちセン\リンク集\利用の回数.txt'
$from = [datetime]'2026-10-19'                         # 数え始めた日
$t = $env:CF_API_TOKEN; if (-not $t) { $t = [Environment]::GetEnvironmentVariable('CF_API_TOKEN', 'User') }
if (-not $t) { return '利用の回数：token がないので、取りませんでした' }
$jst = [TimeZoneInfo]::FindSystemTimeZoneById('Tokyo Standard Time')
$today = [TimeZoneInfo]::ConvertTimeFromUtc([datetime]::UtcNow, $jst).Date
$have = @{}
if (Test-Path $out) { Get-Content $out -Encoding UTF8 | ForEach-Object { if ($_ -match '^(\d{4}-\d\d-\d\d)') { $have[$matches[1]] = 1 } } }
else { Set-Content $out -Encoding UTF8 -Value @('調べ先リンク集　利用の回数（Cloudflare Web Analytics。前日の分を、毎日19時の見回りで書き足す）', '日付　　　　　　　開いた回数　訪問の数（同じ人が続けて使った分を1回と数える）', '') }
$wd = '日月火水木金土'; $added = 0
$s = [math]::Max(1, [int]($today - $from).TotalDays)
for ($d = [math]::Min($s, 7); $d -ge 1; $d--) {
  $day = $today.AddDays(-$d); $key = $day.ToString('yyyy-MM-dd')
  if ($day -lt $from -or $have[$key]) { continue }
  $s0 = [TimeZoneInfo]::ConvertTimeToUtc($day, $jst).ToString('yyyy-MM-ddTHH:mm:ssZ')
  $s1 = [TimeZoneInfo]::ConvertTimeToUtc($day.AddDays(1), $jst).ToString('yyyy-MM-ddTHH:mm:ssZ')
  $q = @{ query = 'query($a:String!,$s:Time!,$e:Time!){viewer{accounts(filter:{accountTag:$a}){rumPageloadEventsAdaptiveGroups(limit:100,filter:{datetime_geq:$s,datetime_lt:$e}){count sum{visits} dimensions{requestHost requestPath}}}}}'
          variables = @{ a = $acct; s = $s0; e = $s1 } } | ConvertTo-Json -Depth 5
  try { $r = Invoke-RestMethod -Method Post -Uri 'https://api.cloudflare.com/client/v4/graphql' -Headers @{ Authorization = "Bearer $t" } -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($q)) }
  catch { return ('利用の回数：取れませんでした（' + $_.Exception.Message + '）') }
  if ($r.errors) { return ('利用の回数：取れませんでした（' + ($r.errors | ForEach-Object { $_.message }) -join ' / ' + '）') }
  $n = 0; $v = 0
  foreach ($g in $r.data.viewer.accounts[0].rumPageloadEventsAdaptiveGroups) {
    if ($g.dimensions.requestPath -like '*/dev/*') { continue }
    $n += $g.count; $v += $g.sum.visits
  }
  Add-Content $out -Encoding UTF8 -Value ('{0}（{1}）　　{2,6}　　{3,6}' -f $key, $wd[[int]$day.DayOfWeek], $n, $v)
  $added++
}
return ('利用の回数：' + $added + ' 日分を書き足しました')
