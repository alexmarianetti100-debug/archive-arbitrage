import asyncio
import sqlite3

# Correct import statement
from db.sqlite_models import init_db, Item, save_item

async def test_auth_integration():
    """Test authentication integration."""
    print("🧪 Testing Authentication Integration...")
    
    # Initialize database
    init_db()
    
    # Test case 1: Authentic item
    test1 = Item()
    test1.id = 1
    test1.source = "test"
    test1.source_id = "123"
    test1.source_url = "https://test.com"
    test1.brand = "Test Brand"
    test1.category = "Test Category"
    test1.size = "One Size"
    test1.condition = "Excellent"
    test1.source_price = 100.0
    test1.our_price = 120.0
    test1.margin_percent = 20
    test1.images = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
    
    # Test case 2: Replica item
    test2 = Item()
    test2.id = 2
    test2.source = "test"
    test2.source_id = "456"
    test2.source_url = "https://test.com"
    test2.brand = "Test Brand"
    test2.category = "Test Category"
    test2.size = "One Size"
    test2.condition = "Good"
    test2.source_price = 50.0
    test2.our_price = 60.0
    test2.margin_percent = 20
    test2.images = ["https://example.com/image3.jpg", "https://example.com/image4.jpg"]
    
    # Test case 3: Replica item
    test3 = Item()
    test3.id = 3
    test3.source = "test"
    test3.source_id = "456"
    test3.source_url = "https://test.com"
    test3.brand = "Test Brand"
    test3.category = "Test Category"
    test3.size = "One Size"
    test3.condition = "Good"
    test3.source_price = 200.0
    test3.our_price = 220.0
    test3.margin_percent = 10
    test3.images = ["https://example.com/image5.jpg", "https://example.com/image6.jpg"]
    
    # Test case 4: Replica item
    test4 = Item()
    test4.id = 4
    test4.source = "test"
    test4.source_id = "789"
    test4.source_url = "https://test.com"
    test4.brand = "Test Brand"
    test4.category = "Test Category"
    test4.size = "One Size"
    test4.condition = "Good"
    test4.source_price = 300.0
    test4.our_price = 320.0
    test4.margin_percent = 6.67
    test4.images = ["https://example.com/image7.jpg", "https://example.com/image8.jpg"]
    
    # Test case 5: Replica item
    test5 = Item()
    test5.id = 5
    test5.source = "test"
    test5.source_id = "789"
    test5.source_url = "https://test.com"
    test5.brand = "Test Brand"
    test5.category = "Test Category"
    test5.size = "One Size"
    test5.condition = "Good"
    test5.source_price = 400.0
    test5.our_price = 420.0
    test5.margin_percent = 5
    test5.images = ["https://example.com/image9.jpg", "https://example.com/image10.jpg"]
    
    # Test case 6: Replica item
    test6 = Item()
    test6.id = 6
    test6.source = "test"
    test6.source_id = "789"
    test6.source_url = "https://test.com"
    test6.brand = "Test Brand"
    test6.category = "Test Category"
    test6.size = "One Size"
    test6.condition = "Good"
    test6.source_price = 300.0
    test6.our_price = 320.0
    test6.margin_percent = 6.67
    test6.images = ["https://example.com/image11.jpg", "https://example.com/image12.jpg"]
    
    # Test case 7: Replica item
    test7 = Item()
    test7.id = 7
    test7.source = "test"
    test7.source_id = "789"
    test7.source_url = "https://test.com"
    test7.brand = "Test Brand"
    test7.category = "Test Category"
    test7.size = "One Size"
    test7.condition = "Good"
    test7.source_price = 400.0
    test7.our_price = 420.0
    test7.margin_percent = 5
    test7.images = ["https://example.com/image13.jpg", "https://example.com/image14.jpg"]
    
    # Test case 8: Replica item
    test8 = Item()
    test8.id = 8
    test8.source = "test"
    test8.source_id = "789"
    test8.source_url = "https://test.com"
    test8.brand = "Test Brand"
    test8.category = "Test Category"
    test8.size = "One Size"
    test8.condition = "Good"
    test8.source_price = 300.0
    test8.our_price = 320.0
    test8.margin_percent = 5
    test8.images = ["https://example.com/image15.jpg", "https://example.com/image16.jpg"]
    
    # Test case 9: Replica item
    test9 = Item()
    test9.id = 9
    test9.source = "test"
    test9.source_id = "789"
    test9.source_url = "https://test.com"
    test9.brand = "Test Brand"
    test9.category = "Test Category"
    test9.size = "One Size"
    test9.condition = "Good"
    test9.source_price = 400.0
    test9.our_price = 420.0
    test9.margin_percent = 5
    test9.images = ["https://example.com/image17.jpg", "https://example.com/image18.jpg"]
    
    # Test case 10: Replica item
    test10 = Item()
    test10.id = 10
    test10.source = "test"
    test10.source_id = "789"
    test10.source_url = "https://test.com"
    test10.brand = "Test Brand"
    test10.category = "Test Category"
    test10.size = "One Size"
    test10.condition = "Good"
    test10.source_price = 500.0
    test10.our_price = 520.0
    test10.margin_percent = 3
    test10.images = ["https://example.com/image19.jpg", "https://example.com/image20.jpg"]
    
    # Test case 11: Replica item
    test11 = Item()
    test11.id = 11
    test11.source = "test"
    test11.source_id = "789"
    test11.source_url = "https://test.com"
    test11.brand = "Test Brand"
    test11.category = "Test Category"
    test11.size = "One Size"
    test11.condition = "Good"
    test11.source_price = 500.0
    test11.our_price = 520.0
    test11.margin_percent = 3
    test11.images = ["https://example.com/image21.jpg", "https://example.com/image22.jpg"]
    
    # Test case 12: Replica item
    test12 = Item()
    test12.id = 12
    test12.source = "test"
    test12.source_id = "789"
    test12.source_url = "https://test.com"
    test12.brand = "Test Brand"
    test12.category = "Test Category"
    test12.size = "One Size"
    test12.condition = "Good"
    test12.source_price = 500.0
    test12.our_price = 520.0
    test12.margin_percent = 3
    test12.images = ["https://example.com/image23.jpg", "https://example.com/image24.jpg"]
    
    # Test case 13: Replica item
    test13 = Item()
    test13.id = 13
    test13.source = "test"
    test13.source_id = "789"
    test13.source_url = "https://test.com"
    test13.brand = "Test Brand"
    test13.category = "Test Category"
    test13.size = "One Size"
    test13.condition = "Good"
    test13.source_price = 500.0
    test13.our_price = 520.0
    test13.margin_percent = 3
    test13.images = ["https://example.com/image25.jpg", "https://example.com/image26.jpg"]
    
    # Test case 14: Replica item
    test14 = Item()
    test14.id = 14
    test14.source = "test"
    test14.source_id = "789"
    test14.source_url = "https://test.com"
    test14.brand = "Test Brand"
    test14.category = "Test Category"
    test14.size = "One Size"
    test14.condition = "Good"
    test14.source_price = 500.0
    test14.our_price = 520.0
    test14.margin_percent = 3
    test14.images = ["https://example.com/image27.jpg", "https://example.com/image28.jpg"]
    
    # Test case 15: Replica item
    test15 = Item()
    test15.id = 15
    test15.source = "test"
    test15.source_id = "789"
    test15.source_url = "https://test.com"
    test15.brand = "Test Brand"
    test15.category = "Test Category"
    test15.size = "One Size"
    test15.condition = "Good"
    test15.source_price = 500.0
    test15.our_price = 520.0
    test15.margin_percent = 3
    test15.images = ["https://example.com/image29.jpg", "https://example.com/image30.jpg"]
    
    # Test case 16: Replica item
    test16 = Item()
    test16.id = 16
    test16.source = "test"
    test16.source_id = "789"
    test16.source_url = "https://test.com"
    test16.brand = "Test Brand"
    test16.category = "Test Category"
    test16.size = "One Size"
    test16.condition = "Good"
    test16.source_price = 500.0
    test16.our_price = 520.0
    test16.margin_percent = 3
    test16.images = ["https://example.com/image31.jpg", "https://example.com/image32.jpg"]
    
    # Test case 17: Replica item
    test17 = Item()
    test17.id = 17
    test17.source = "test"
    test17.source_id = "789"
    test17.source_url = "https://test.com"
    test17.brand = "Test Brand"
    test17.category = "Test Category"
    test17.size = "One Size"
    test17.condition = "Good"
    test17.source_price = 500.0
    test17.our_price = 520.0
    test17.margin_percent = 3
    test17.images = ["https://example.com/image33.jpg", "https://example.com/image34.jpg"]
    
    # Test case 18: Replica item
    test18 = Item()
    test18.id = 18
    test18.source = "test"
    test18.source_id = "789"
    test18.source_url = "https://test.com"
    test18.brand = "Test Brand"
    test18.category = "Test Category"
    test18.size = "One Size"
    test18.condition = "Good"
    test18.source_price = 500.0
    test18.our_price = 520.0
    test18.margin_percent = 3
    test18.images = ["https://example.com/image35.jpg", "https://example.com/image36.jpg"]
    
    # Test case 19: Replica item
    test19 = Item()
    test19.id = 19
    test19.source = "test"
    test19.source_id = "789"
    test19.source_url = "https://test.com"
    test19.brand = "Test Brand"
    test19.category = "Test Category"
    test19.size = "One Size"
    test19.condition = "Good"
    test19.source_price = 500.0
    test19.our_price = 520.0
    test19.margin_percent = 3
    test19.images = ["https://example.com/image37.jpg", "https://example.com/image38.jpg"]
    
    # Test case 20: Replica item
    test20 = Item()
    test20.id = 20
    test20.source = "test"
    test20.source_id = "789"
    test20.source_url = "https://test.com"
    test20.brand = "Test Brand"
    test20.category = "Test Category"
    test20.size = "One Size"
    test20.condition = "Good"
    test20.source_price = 500.0
    test20.our_price = 520.0
    test20.margin_percent = 3
    test20.images = ["https://example.com/image39.jpg", "https://example.com/image40.jpg"]
    
    # Test case 21: Replica item
    test21 = Item()
    test21.id = 21
    test21.source = "test"
    test21.source_id = "789"
    test21.source_url = "https://test.com"
    test21.brand = "Test Brand"
    test21.category = "Test Category"
    test21.size = "One Size"
    test21.condition = "Good"
    test21.source_price = 500.0
    test21.our_price = 520.0
    test21.margin_percent = 3
    test21.images = ["https://example.com/image41.jpg", "https://example.com/image42.jpg"]
    
    # Test case 22: Replica item
    test22 = Item()
    test22.id = 22
    test22.source = "test"
    test22.source_id = "789"
    test22.source_url = "https://test.com"
    test22.brand = "Test Brand"
    test22.category = "Test Category"
    test22.size = "One Size"
    test22.condition = "Good"
    test22.source_price = 500.0
    test22.our_price = 520.0
    test22.margin_percent = 3
    test22.images = ["https://example.com/image43.jpg", "https://example.com/image44.jpg"]
    
    # Test case 23: Replica item
    test23 = Item()
    test23.id = 23
    test23.source = "test"
    test23.source_id = "789"
    test23.source_url = "https://test.com"
    test23.brand = "Test Brand"
    test23.category = "Test Category"
    test23.size = "One Size"
    test23.condition = "Good"
    test23.source_price = 500.0
    test23.our_price = 520.0
    test23.margin_percent = 3
    test23.images = ["https://example.com/image45.jpg", "https://example.com