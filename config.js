import fs from 'fs';
import dotenv from 'dotenv';
dotenv.config({ path: '.env' });

function getBoolean(str, defaultValue = false) {
  return str ? str.toLowerCase() === 'true' : defaultValue;
}

function getFile(filePath) {
  if (filePath !== undefined && filePath) {
    try {
      if (fs.existsSync(filePath)) {
        return fs.readFileSync(filePath);
      }
    } catch (error) {
      console.error('Failed to read file', filePath, error);
    }
  }
  return null;
}

function getFileEnv(envVariable) {
  const origVar = process.env[envVariable];
  const fileVar = process.env[envVariable + '_FILE'];
  if (fileVar) {
    const file = getFile(fileVar);
    if (file) {
      return file.toString().split(/\r?\n/)[0].trim();
    }
  }
  return origVar;
}

module.exports = {
  mongodb: {
    server: getFileEnv('ME_CONFIG_MONGODB_SERVER') || 'mongo',
    port: getFileEnv('ME_CONFIG_MONGODB_PORT') || 27017,
    adminUsername: getFileEnv('ME_CONFIG_MONGODB_ADMINUSERNAME') || 'lhs',
    adminPassword: getFileEnv('ME_CONFIG_MONGODB_ADMINPASSWORD') || 'batata123',
    useBasicAuth: getBoolean(getFileEnv('ME_CONFIG_BASICAUTH_ENABLED'), true),
    basicAuth: {
      username: getFileEnv('ME_CONFIG_BASICAUTH_USERNAME') || 'admin',
      password: getFileEnv('ME_CONFIG_BASICAUTH_PASSWORD') || 'pass',
    },
  },
  site: {
    baseUrl: getFileEnv('ME_CONFIG_SITE_BASEURL') || '/mongo-express/',
    host: getFileEnv('ME_CONFIG_SITE_HOST') || '0.0.0.0',
    port: getFileEnv('ME_CONFIG_SITE_PORT') || 8081,
    cookieSecret: getFileEnv('ME_CONFIG_SITE_COOKIESECRET') || 'cookiesecret',
    sessionSecret: getFileEnv('ME_CONFIG_SITE_SESSIONSECRET') || 'sessionsecret',
    cookieKeyName: 'mongo-express',
    requestSizeLimit: getFileEnv('ME_CONFIG_REQUEST_SIZE') || '100kb',
  },
  options: {
    editCodeMirrorOptions: {
      tabSize: 2,
      lineNumbers: true,
      theme: 'rubyblue',
    },
    readOnly: getBoolean(getFileEnv('ME_CONFIG_OPTIONS_READONLY'), false),
    noDelete: getBoolean(getFileEnv('ME_CONFIG_OPTIONS_NO_DELETE'), false),
  },
};
