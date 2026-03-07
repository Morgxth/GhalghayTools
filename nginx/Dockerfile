FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html
COPY launcher.js /usr/share/nginx/html/launcher.js

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
