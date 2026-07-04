const neo4jDriver = require('../config/neo4j');
const axios = require('axios');

const PYTHON_WORKER_URL = process.env.PYTHON_WORKER_URL || 'http://localhost:8000';

exports.getRepos = async (req, res) => {
    const session = neo4jDriver.session();
    try {
        const result = await session.run(`
            MATCH (r:Repository)
            OPTIONAL MATCH (n)-[:BELONGS_TO*]->(r)
            OPTIONAL MATCH (a)-[:CALLS|:REFERENCES]->(b)-[:BELONGS_TO*]->(r)
            RETURN r.id AS id, r.name AS name, count(DISTINCT n) AS nodes, count(DISTINCT a) AS edges
        `);
        
        const repos = result.records.map(record => ({
            id: record.get('id'),
            name: record.get('name') || record.get('id'),
            status: "Indexed", // Hardcoded for now
            lastSync: "Just now",
            branch: "main",
            nodes: record.get('nodes').toNumber(),
            edges: record.get('edges').toNumber(),
        }));
        
        res.json(repos);
    } catch (error) {
        console.error('Error fetching repos:', error);
        res.status(500).json({ error: error.message });
    } finally {
        await session.close();
    }
};

exports.getGraph = async (req, res) => {
    const { repoId } = req.params;
    const session = neo4jDriver.session();
    try {
        // Fetch nodes
        const nodesResult = await session.run(
            `MATCH (n) WHERE n.repo_id = $repoId RETURN n.id AS id, labels(n) AS labels, n.name AS name`,
            { repoId }
        );
        
        // Fetch edges
        const edgesResult = await session.run(
            `MATCH (a)-[r]->(b) WHERE a.repo_id = $repoId AND b.repo_id = $repoId 
             RETURN a.id AS source, b.id AS target, type(r) AS type`,
            { repoId }
        );

        const nodes = nodesResult.records.map(record => {
            const labels = record.get('labels');
            let group = 1;
            if (labels.includes('File')) group = 1;
            else if (labels.includes('Class')) group = 2;
            else if (labels.includes('Function')) group = 3;
            else if (labels.includes('Variable')) group = 4;
            
            return {
                id: record.get('id'),
                label: record.get('name') || record.get('id').split('/').pop(),
                group,
                val: group === 1 ? 5 : (group === 2 ? 4 : 2) // Rough sizing based on type
            };
        });

        const links = edgesResult.records.map(record => ({
            source: record.get('source'),
            target: record.get('target'),
            label: record.get('type')
        }));

        res.json({ nodes, links });
    } catch (error) {
        console.error('Error fetching graph:', error);
        res.status(500).json({ error: error.message });
    } finally {
        await session.close();
    }
};

exports.queryAgent = async (req, res) => {
    const { repoId, question } = req.body;
    if (!repoId || !question) {
        return res.status(400).json({ error: 'repoId and question are required' });
    }

    try {
        // Proxy to Python LangGraph Agent Worker
        const response = await axios.post(`${PYTHON_WORKER_URL}/query`, {
            repo_id: repoId,
            question,
            top_k: 5
        });

        res.json(response.data);
    } catch (error) {
        console.error('Error querying agent:', error.message);
        res.status(500).json({ error: 'Failed to communicate with AI worker' });
    }
};
