FROM nginx:alpine

# 复制静态文件
COPY . /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# HF Spaces 要求监听7860端口
EXPOSE 7860

CMD ["nginx", "-g", "daemon off;"]
