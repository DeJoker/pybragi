class A:
    def __init__(self):
        print("A.__init__ called")

class B(A):
    def __init__(self):
        super().__init__()
        print("B.__init__ called")

    def who_am_i(self):
        """
        这个方法在 B 类中定义，但可以显示调用它的对象的真实类型。
        """
        print(f"Executing method defined in class B")
        print(f"The real type of the instance is: {type(self)}")
        print(f"Also can be accessed via __class__: {self.__class__}")
        print(f"The class name is: {self.__class__.__name__}")

class C(B):
    def __init__(self):
        super().__init__()
        print("C.__init__ called")

# --- 测试 ---

print("Creating an instance of C...")
c_instance = C()
# 输出:
# A.__init__ called
# B.__init__ called
# C.__init__ called

print("\nCalling the 'who_am_i' method on the C instance...")
c_instance.who_am_i()
# 输出:
# Executing method defined in class B
# The real type of the instance is: <class '__main__.C'>
# Also can be accessed via __class__: <class '__main__.C'>
# The class name is: C