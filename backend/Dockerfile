FROM node:20

RUN apt-get update && apt-get install -y python3

WORKDIR /app

COPY package.json ./
COPY server.js ./
COPY script.coleta.py ./

RUN npm install
RUN python3 script.coleta.py

EXPOSE 3001

CMD ["npm", "start"]
