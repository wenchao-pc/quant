FROM nginx:alpine

# 复制所有静态文件到nginx默认目录
COPY . /usr/share/nginx/html

# nginx配置：SPA友好 + 中文charset + 缓存策略
RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;
    charset utf-8;

    # JSON允许跨域（供其他服务调用data.json）
    location ~* \.json$ {
        add_header Access-Control-Allow-Origin *;
        add_header Cache-Control "no-cache, must-revalidate";
    }

    # HTML不缓存（每次生成新报告）
    location ~* \.html$ {
        add_header Cache-Control "no-cache, must-revalidate";
    }

    # 静态资源缓存7天
    location ~* \.(css|js|png|jpg|ico|svg)$ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # 所有路径回退到index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
