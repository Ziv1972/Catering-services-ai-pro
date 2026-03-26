process.env.NEXT_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://courteous-amazement-production-02e2.up.railway.app';
process.chdir(__dirname + '/../frontend');
process.argv = ['node', 'next', 'dev'];
require('../frontend/node_modules/next/dist/bin/next');
