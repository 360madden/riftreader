[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [int]$Port,

    [Parameter(Mandatory = $true)]
    [string]$RoutesPath,

    [int]$MaxRequests = 16
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$routes = Get-Content -LiteralPath $RoutesPath -Raw | ConvertFrom-Json -Depth 100
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
$listener.Start()

try {
    for ($i = 0; $i -lt $MaxRequests; $i++) {
        $client = $listener.AcceptTcpClient()
        try {
            $stream = $client.GetStream()
            $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::ASCII, $false, 1024, $true)
            $requestLine = $reader.ReadLine()
            while ($null -ne ($line = $reader.ReadLine()) -and $line.Length -gt 0) {
            }

            $path = '/'
            if (-not [string]::IsNullOrWhiteSpace($requestLine)) {
                $parts = $requestLine.Split(' ')
                if ($parts.Length -ge 2) {
                    $path = $parts[1]
                }
            }

            $routeProperty = $routes.PSObject.Properties[$path]
            $statusCode = 404
            $bodyObject = [ordered]@{ ok = $false; error = 'not found' }
            if ($null -ne $routeProperty) {
                $statusCode = [int]$routeProperty.Value.statusCode
                $bodyObject = $routeProperty.Value.body
            }

            $body = $bodyObject | ConvertTo-Json -Depth 100 -Compress
            $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)
            $header = "HTTP/1.1 $statusCode Test`r`nContent-Type: application/json`r`nContent-Length: $($bodyBytes.Length)`r`nConnection: close`r`n`r`n"
            $headerBytes = [System.Text.Encoding]::ASCII.GetBytes($header)
            try {
                $stream.Write($headerBytes, 0, $headerBytes.Length)
                $stream.Write($bodyBytes, 0, $bodyBytes.Length)
                $stream.Flush()
            }
            catch {
                # Test clients may close a readiness probe connection early; keep
                # the server alive for the real request.
            }
        }
        finally {
            $client.Dispose()
        }
    }
}
finally {
    $listener.Stop()
}
