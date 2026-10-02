// Event Hubs namespace + hub + free App Service (F1) running the Python (FastAPI) app.
@description('Short prefix for resource names (lowercase letters/numbers).')
param baseName string = 'hotellab'
param location string = 'centralindia'
@description('Basic = cheapest, no Kafka. Use Standard to enable the Kafka endpoint (paid).')
@allowed(['Basic', 'Standard'])
param eventHubSku string = 'Standard'

var suffix = uniqueString(resourceGroup().id)
var hubName = 'hotel-events'

resource ns 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: '${baseName}-ehns-${suffix}'
  location: location
  sku: { name: eventHubSku, tier: eventHubSku, capacity: 1 }
  properties: { minimumTlsVersion: '1.2' }
}

resource hub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: ns
  name: hubName
  properties: { partitionCount: 2, messageRetentionInDays: 1 }
}

// Hub-scoped key: the connection string includes EntityPath=hotel-events
resource rule 'Microsoft.EventHub/namespaces/eventhubs/authorizationRules@2024-01-01' = {
  parent: hub
  name: 'app'
  properties: { rights: ['Listen', 'Send'] }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${baseName}-plan-${suffix}'
  location: location
  kind: 'linux'
  sku: { name: 'B1', tier: 'Basic' }
  properties: { reserved: true }
}

resource web 'Microsoft.Web/sites@2023-12-01' = {
  name: '${baseName}-web-${suffix}'
  location: location
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'gunicorn -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app'
      alwaysOn: false // not available on the free tier
      appSettings: [
        { name: 'EVENTHUB_CONNECTION_STRING', value: rule.listKeys().primaryConnectionString }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' } // install requirements.txt on deploy
      ]
    }
  }
}

output webAppName string = web.name
output webAppUrl string = 'https://${web.properties.defaultHostName}'
output eventHubNamespace string = ns.name
