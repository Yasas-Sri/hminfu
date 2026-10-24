FROM node:22-alpine
WORKDIR /srv/frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]
