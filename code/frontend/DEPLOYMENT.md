# SIGNAL Frontend Deployment Guide

## Production Build

### Build the Application

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory with:
- Minified JavaScript bundles
- Optimized CSS
- Asset hashing for cache busting
- Source maps for debugging

### Preview Production Build Locally

```bash
npm run preview
```

Serves the production build at `http://localhost:4173`

## Deployment Options

### Option 1: Static File Server (Recommended for MVP)

The built files in `dist/` are static and can be served by any web server.

#### Nginx

```nginx
server {
    listen 80;
    server_name signal.example.com;
    root /var/www/signal/dist;
    index index.html;

    # SPA routing - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to backend
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

#### Apache

```apache
<VirtualHost *:80>
    ServerName signal.example.com
    DocumentRoot /var/www/signal/dist

    <Directory /var/www/signal/dist>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted

        # SPA routing
        RewriteEngine On
        RewriteBase /
        RewriteRule ^index\.html$ - [L]
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteRule . /index.html [L]
    </Directory>

    # API proxy
    ProxyPass /api http://localhost:8000/api
    ProxyPassReverse /api http://localhost:8000/api
</VirtualHost>
```

### Option 2: Vercel (Easiest for Demo)

1. Install Vercel CLI:
```bash
npm i -g vercel
```

2. Deploy:
```bash
vercel
```

3. Configure API proxy in `vercel.json`:
```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://your-backend.com/api/:path*"
    }
  ]
}
```

### Option 3: Netlify

1. Install Netlify CLI:
```bash
npm i -g netlify-cli
```

2. Deploy:
```bash
netlify deploy --prod
```

3. Configure redirects in `netlify.toml`:
```toml
[[redirects]]
  from = "/api/*"
  to = "https://your-backend.com/api/:splat"
  status = 200

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### Option 4: Docker

Create `Dockerfile`:

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Create `nginx.conf`:

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Build and run:

```bash
docker build -t signal-frontend .
docker run -p 3000:80 signal-frontend
```

### Option 5: Docker Compose (Full Stack)

Create `docker-compose.yml` in project root:

```yaml
version: '3.8'

services:
  backend:
    build: ./code/backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./data/signal.db
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./data:/app/data

  frontend:
    build: ./code/frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://backend:8000
```

Run:

```bash
docker-compose up -d
```

## Environment Configuration

### Development
- API proxied through Vite dev server
- Hot module replacement enabled
- Source maps for debugging

### Production
- API URL configured via environment variable or proxy
- Minified bundles
- No source maps (optional)

### Environment Variables

Create `.env.production`:

```bash
VITE_API_URL=https://api.signal.example.com
```

Access in code:

```typescript
const API_URL = import.meta.env.VITE_API_URL || '/api'
```

## Performance Optimization

### Bundle Analysis

```bash
npm run build -- --mode analyze
```

### Optimization Checklist

- [x] Code splitting by route
- [x] Minification (Vite default)
- [x] Tree shaking (Vite default)
- [x] Asset optimization
- [ ] Image lazy loading (add if needed)
- [ ] Service worker for offline (future)
- [ ] CDN for static assets (production)

### Lighthouse Scores Target

- Performance: 90+
- Accessibility: 95+
- Best Practices: 95+
- SEO: 90+

## Monitoring

### Error Tracking

Add Sentry (optional):

```bash
npm install @sentry/react
```

```typescript
import * as Sentry from "@sentry/react"

Sentry.init({
  dsn: "your-sentry-dsn",
  environment: import.meta.env.MODE,
})
```

### Analytics

Add Google Analytics (optional):

```html
<!-- In index.html -->
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_MEASUREMENT_ID');
</script>
```

## Security Considerations

### Content Security Policy

Add to `index.html`:

```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; 
               script-src 'self' 'unsafe-inline'; 
               style-src 'self' 'unsafe-inline'; 
               img-src 'self' data: https:; 
               connect-src 'self' https://api.signal.example.com;">
```

### HTTPS

Always use HTTPS in production:
- Let's Encrypt for free SSL certificates
- Cloudflare for CDN + SSL
- Vercel/Netlify provide SSL automatically

### API Security

- Use CORS properly on backend
- Implement rate limiting
- Add authentication tokens
- Validate all inputs

## Troubleshooting

### Build Fails

```bash
# Clear cache and rebuild
rm -rf node_modules dist
npm install
npm run build
```

### API Connection Issues

- Check CORS configuration on backend
- Verify API URL in environment variables
- Test API endpoints directly with curl
- Check browser network tab for errors

### Routing Issues (404 on Refresh)

- Ensure server is configured for SPA routing
- All routes should serve `index.html`
- Check `.htaccess` or nginx config

### Performance Issues

- Enable gzip compression on server
- Use CDN for static assets
- Implement caching headers
- Lazy load images and heavy components

## Rollback Strategy

### Version Tagging

```bash
git tag -a v1.0.0 -m "Release 1.0.0"
git push origin v1.0.0
```

### Quick Rollback

```bash
# Checkout previous version
git checkout v1.0.0

# Rebuild and redeploy
npm run build
# Deploy dist/ to server
```

## Maintenance

### Dependency Updates

```bash
# Check for updates
npm outdated

# Update all dependencies
npm update

# Update major versions (carefully)
npm install react@latest react-dom@latest
```

### Security Audits

```bash
# Check for vulnerabilities
npm audit

# Fix automatically
npm audit fix
```

## Hackathon Demo Deployment

For quick demo deployment:

1. **Vercel** (fastest):
   ```bash
   vercel --prod
   ```

2. **Netlify** (easy):
   ```bash
   netlify deploy --prod
   ```

3. **GitHub Pages** (free):
   - Push to GitHub
   - Enable GitHub Pages in repo settings
   - Set build directory to `dist`

4. **Local Network** (no internet):
   ```bash
   npm run build
   npx serve dist -p 3000
   ```

## Post-Hackathon Production

For real production deployment:

1. Set up proper CI/CD (GitHub Actions, GitLab CI)
2. Implement staging environment
3. Add monitoring and alerting
4. Set up automated backups
5. Configure CDN (Cloudflare, AWS CloudFront)
6. Implement authentication
7. Add rate limiting
8. Set up logging aggregation
9. Create runbooks for common issues
10. Document deployment process

## Support

For deployment issues:
- Check Vite documentation: https://vitejs.dev/guide/
- React Router deployment: https://reactrouter.com/en/main/guides/deployment
- Platform-specific guides (Vercel, Netlify, etc.)
