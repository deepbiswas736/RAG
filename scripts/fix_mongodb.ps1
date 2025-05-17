# PowerShell script to fix MongoDB replica set issues

Write-Host "Starting MongoDB fix script..." -ForegroundColor Cyan

# Function to wait for a condition with timeout
function Wait-For {
    param (
        [ScriptBlock]$Condition,
        [int]$TimeoutSeconds = 60,
        [string]$Activity = "Waiting for condition"
    )
    
    $start = Get-Date
    $timeSpan = New-TimeSpan -Seconds $TimeoutSeconds
    $progressParams = @{
        Activity = $Activity
        Status = "Waiting..."
        PercentComplete = 0
    }
    
    while (-not (& $Condition)) {
        $now = Get-Date
        $elapsed = $now - $start
        if ($elapsed -gt $timeSpan) {
            Write-Host "Timeout after $TimeoutSeconds seconds" -ForegroundColor Red
            return $false
        }
        
        $progressParams.PercentComplete = ($elapsed.TotalSeconds / $timeSpan.TotalSeconds) * 100
        Write-Progress @progressParams
        
        Start-Sleep -Seconds 1
    }
    
    Write-Progress -Activity $Activity -Completed
    return $true
}

# Check if MongoDB container is running
$mongoContainer = docker ps --filter "name=mongodb" --format "{{.Names}}"
if (-not $mongoContainer) {
    Write-Host "MongoDB container is not running." -ForegroundColor Red
    Write-Host "Starting containers..." -ForegroundColor Yellow
    
    docker-compose -f e:\code\experimental\RAG\docker-compose.yml down
    Start-Sleep -Seconds 5
    docker-compose -f e:\code\experimental\RAG\docker-compose.yml up -d
    
    # Wait for container to start
    if (-not (Wait-For { 
            $container = docker ps --filter "name=mongodb" --format "{{.Names}}"
            return $container -ne $null
        } -TimeoutSeconds 60 -Activity "Waiting for MongoDB container to start")) {
        Write-Host "Failed to start MongoDB container" -ForegroundColor Red
        exit 1
    }
    
    $mongoContainer = docker ps --filter "name=mongodb" --format "{{.Names}}"
    Write-Host "MongoDB container started: $mongoContainer" -ForegroundColor Green
    
    # Wait for MongoDB to become responsive
    Write-Host "Waiting for MongoDB to become responsive..." -ForegroundColor Yellow
    if (-not (Wait-For { 
            $result = docker exec $mongoContainer mongosh --quiet --eval "db.adminCommand('ping')" 2>$null
            return $result -like "*ok*:*1*"
        } -TimeoutSeconds 90 -Activity "Waiting for MongoDB to become responsive")) {
        Write-Host "MongoDB is not responding in time" -ForegroundColor Red
        exit 1
    }
}

# Initialize replica set
Write-Host "Initializing replica set..." -ForegroundColor Yellow
$initResult = docker exec $mongoContainer mongosh --quiet --eval "
try {
  const status = rs.status();
  if (status.ok === 1) {
    print(JSON.stringify({status: 'already_initialized', ok: true}));
  } else {
    print(JSON.stringify({status: 'error', message: status.codeName}));
  }
} catch (e) {
  if (e.codeName === 'NotYetInitialized') {
    const result = rs.initiate({
      _id: 'rs0',
      members: [{ _id: 0, host: 'mongodb:27017' }]
    });
    print(JSON.stringify({status: 'initialized', result: result}));
  } else {
    print(JSON.stringify({status: 'error', message: e.message}));
  }
}"

if ($initResult) {
    try {
        $parsedResult = $initResult | ConvertFrom-Json
        
        if ($parsedResult.status -eq "already_initialized") {
            Write-Host "Replica set is already initialized" -ForegroundColor Green
        }
        elseif ($parsedResult.status -eq "initialized") {
            if ($parsedResult.result.ok -eq 1) {
                Write-Host "Replica set initialized successfully" -ForegroundColor Green
            } else {
                Write-Host "Failed to initialize replica set: $($parsedResult.result.errmsg)" -ForegroundColor Red
            }
        }
        else {
            Write-Host "Error: $($parsedResult.message)" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "Error parsing MongoDB output: $_" -ForegroundColor Red
        Write-Host "Raw output: $initResult" -ForegroundColor Yellow
    }
}

# Wait for replica set to stabilize
Write-Host "Waiting for replica set to stabilize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Create admin user if needed
Write-Host "Creating admin user if not exists..." -ForegroundColor Yellow
$createUserResult = docker exec $mongoContainer mongosh --quiet --eval "
try {
  const adminDb = db.getSiblingDB('admin');
  const users = adminDb.getUsers();
  let userExists = false;
  
  for (let i = 0; i < users.users.length; i++) {
    if (users.users[i].user === 'user') {
      userExists = true;
      break;
    }
  }
  
  if (!userExists) {
    const result = adminDb.createUser({
      user: 'user',
      pwd: 'password',
      roles: [
        { role: 'userAdminAnyDatabase', db: 'admin' },
        { role: 'readWriteAnyDatabase', db: 'admin' },
        { role: 'dbAdminAnyDatabase', db: 'admin' },
        { role: 'clusterAdmin', db: 'admin' }
      ]
    });
    print(JSON.stringify({status: 'created', result: result}));
  } else {
    print(JSON.stringify({status: 'exists'}));
  }
} catch (e) {
  print(JSON.stringify({status: 'error', message: e.message}));
}"

if ($createUserResult) {
    try {
        $parsedResult = $createUserResult | ConvertFrom-Json
        
        if ($parsedResult.status -eq "created") {
            Write-Host "Admin user created successfully" -ForegroundColor Green
        }
        elseif ($parsedResult.status -eq "exists") {
            Write-Host "Admin user already exists" -ForegroundColor Green
        }
        else {
            Write-Host "Error creating admin user: $($parsedResult.message)" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "Error parsing MongoDB output: $_" -ForegroundColor Red
        Write-Host "Raw output: $createUserResult" -ForegroundColor Yellow
    }
}

# Check final status
Write-Host "`nChecking final status..." -ForegroundColor Cyan
$statusResult = docker exec $mongoContainer mongosh --quiet --eval "
try {
  const status = rs.status();
  print(JSON.stringify({ok: status.ok, set: status.set, members: status.members}));
} catch (e) {
  print(JSON.stringify({ok: 0, error: e.message}));
}"

if ($statusResult) {
    try {
        $parsedStatus = $statusResult | ConvertFrom-Json
        
        if ($parsedStatus.ok -eq 1) {
            Write-Host "✓ Replica set '$($parsedStatus.set)' is now correctly configured and operational" -ForegroundColor Green
            
            Write-Host "`nMembers:" -ForegroundColor Cyan
            foreach ($member in $parsedStatus.members) {
                $stateColor = switch ($member.stateStr) {
                    "PRIMARY" { "Yellow" }
                    "SECONDARY" { "Green" }
                    default { "White" }
                }
                
                $healthStatus = if ($member.health -eq 1) { "healthy" } else { "unhealthy" }
                Write-Host "  - $($member.name): $($member.stateStr) ($healthStatus)" -ForegroundColor $stateColor
            }
            
            Write-Host "`nMongoDB is now ready for use!" -ForegroundColor Green
        } else {
            Write-Host "! Replica set is still not configured properly: $($parsedStatus.error)" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "Error parsing MongoDB status output: $_" -ForegroundColor Red
        Write-Host "Raw output: $statusResult" -ForegroundColor Yellow
    }
}
