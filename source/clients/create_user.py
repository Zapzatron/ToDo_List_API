import httpx
import asyncio


TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass"


async def main():
    async with httpx.AsyncClient() as client:
        response = await client.post("http://127.0.0.35:8000/users/create", json={"username": TEST_USERNAME,
                                                                                  "password": TEST_PASSWORD})

        print(response.status_code, response.json())


if __name__ == "__main__":
    asyncio.run(main())
