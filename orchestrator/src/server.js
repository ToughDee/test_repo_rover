require('dotenv').config();
const express = require('express');
const cors = require('cors');
const neo4j = require('neo4j-driver');
const connectMongoDB = require('./config/db');
const syncRoutes = require('./routes/syncRoutes');
const queryRoutes = require('./routes/queryRoutes');

// Initialize Express App
const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Connect to MongoDB
connectMongoDB();

const driver = require('./config/neo4j');
try {
    driver.verifyConnectivity().then(() => console.log('✅ Neo4j Driver Initialized'));
} catch (error) {
    console.error('❌ Failed to initialize Neo4j Driver:', error.message);
}

// Health Check Endpoint
app.get('/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        service: 'orchestrator', 
        timestamp: new Date().toISOString() 
    });
});

// Mount Routes
app.use('/api', syncRoutes);
app.use('/api', queryRoutes);

// Start Server
app.listen(PORT, () => {
    console.log(`🚀 Node Orchestrator running on http://localhost:${PORT}`);
});
