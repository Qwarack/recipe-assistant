FROM node:22-slim

RUN npm install --global obsidian-headless

WORKDIR /vault

CMD ["ob", "sync", "--continuous", "--path", "/vault"]
