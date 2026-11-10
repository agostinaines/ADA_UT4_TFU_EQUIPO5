
FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --omit=dev

COPY index.js ./

EXPOSE 5005

CMD ["npm", "start"]
