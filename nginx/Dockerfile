FROM nginx:alpine

RUN apk add --no-cache gettext

COPY nginx.conf /etc/nginx/nginx.conf.template
COPY index.html /usr/share/nginx/html/index.html
COPY launcher.js /usr/share/nginx/html/launcher.js

# Подставляем env-переменные в nginx.conf при старте
CMD ["/bin/sh", "-c", "envsubst '${SPELL_HOST} ${SPELL_PORT} ${TRANSLATE_HOST} ${TRANSLATE_PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]

EXPOSE 80
