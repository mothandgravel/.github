FROM node:24.19.0-bookworm-slim@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df
ENV NODE_ENV=production PORT=8787 ENQUIRIES_ENABLED=false DATABASE_PATH=/data/enquiries.sqlite
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && mkdir /data && chown node:node /data
COPY *.mjs ./
USER node
EXPOSE 8787
VOLUME /data
CMD ["node", "server.mjs"]
